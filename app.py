import os
import sys

from flask import Flask
from flask import request, current_app, Blueprint, send_from_directory, render_template, after_this_request, jsonify, g, abort

from haversine import haversine, Unit
from math import sqrt

import redis

import gzip
import functools
import argparse

from interpolate import loader, AQIInterpolator, aqiFromPM
from datetime import datetime

app = Flask('aqi')

def get_redis():
   if 'redis' not in g:
      r = redis.Redis(host=current_app.config['REDIS_HOST'],port=int(current_app.config['REDIS_PORT']),password=current_app.config.get('REDIS_PASSWORD'))
      g.redis = r
   return g.redis

def gzipped(f):
   @functools.wraps(f)
   def view_func(*args, **kwargs):
      @after_this_request
      def zipper(response):
         if not current_app.config.get('COMPRESS'):
            return response

         accept_encoding = request.headers.get('Accept-Encoding', '')

         if 'gzip' not in accept_encoding.lower():
            return response

         response.direct_passthrough = False

         if (response.status_code < 200 or
             response.status_code >= 300 or
             'Content-Encoding' in response.headers):
            return response
         gzip_buffer = BytesIO()
         gzip_file = gzip.GzipFile(mode='wb',
                                   fileobj=gzip_buffer)
         gzip_file.write(response.data)
         gzip_file.close()

         response.data = gzip_buffer.getvalue()
         response.headers['Content-Encoding'] = 'gzip'
         response.headers['Vary'] = 'Accept-Encoding'
         response.headers['Content-Length'] = len(response.data)

         return response

      return f(*args, **kwargs)

   return view_func

aqi = Blueprint('aqi',__name__)

@aqi.route('/')
def index():
   return render_template('main.html')

@aqi.route('/api/load')
def load():
   urls = request.args.getlist('url')
   start = datetime.now()
   bayarea = [38.41646632263371,-124.02669995117195,36.98663820370443,-120.12930004882817]
   interpolator = loader(bayarea,urls)
   loaded_at = datetime.now()
   grid = interpolator.generate_grid(method='linear')
   interpolated_at = datetime.now()
   loading_time = loaded_at - start
   interpolation_time = interpolated_at - loaded_at
   print('Loading {}s, interpolation {}s'.format(loading_time.total_seconds(),interpolation_time.total_seconds()))
   return jsonify({
      'bounds' : bayarea,
      'resolution' : interpolator.resolution,
      'grid' : grid.tolist()
   })

@aqi.route('/api/partition/<partition_set>/at')
def partition(partition_set):
   client = get_redis()

   lat = float(request.args.get('lat'))
   lon = float(request.args.get('lon'))
   radius = int(request.args.get('radius'))
   unit = request.args.get('unit')

   if lat is None or lon is None or radius is None:
      abort(400)

   key = current_app.config['KEY_PREFIX'] + partition_set

   result = client.georadius(key,lon,lat,radius,unit=unit,withcoord=True)

   data = []
   for key, pos in result:
      sensor = key.decode('utf-8').split(':')
      data.append([sensor[0],int(sensor[1]),pos[1],pos[0]])

   return jsonify(data)

@aqi.route('/api/partition/<partition_set>/interpolate')
def interpolate(partition_set):
   client = get_redis()

   #bayarea = [38.41646632263371,-124.02669995117195,36.98663820370443,-120.12930004882817]

   nwlat = float(request.args.get('nwlat'))
   nwlon = float(request.args.get('nwlon'))
   selat = float(request.args.get('selat'))
   selon = float(request.args.get('selon'))

   method = request.args.get('method','linear')


   if nwlat is None or nwlon is None or selat is None or selon is None:
      abort(400)

   lat_size = abs(nwlat - selat)
   lon_size = abs(nwlon - selon)
   scale = 0
   if lon_size<2.0:
      scale = 2.0/lon_size/2

   interpolation_bounds = [nwlat + lat_size*scale, nwlon - lon_size*scale, selat - lat_size*scale, selon + lon_size*scale]

   center = (nwlat - lat_size/2, nwlon + lon_size/2)

   radius = haversine(center,(interpolation_bounds[0],interpolation_bounds[1]),unit=Unit.KILOMETERS)

   key = current_app.config['KEY_PREFIX'] + partition_set

   result = client.georadius(key,center[1],center[0],radius,unit='km',withcoord=True)

   bounds = [nwlat,nwlon,selat,selon]

   print(bounds)
   print(interpolation_bounds)


   interpolator = AQIInterpolator(interpolation_bounds,mesh_size=200,resolution=None)
   print(interpolator.resolution)
   for key, pos in result:
      sensor = key.decode('utf-8').split(',')
      # pm_2
      pm_2 = float(sensor[3])
      interpolator.add(pos[1],pos[0],[aqiFromPM(pm_2)])

   grid = interpolator.generate_grid(method=method,index=0)
   return jsonify({
      'bounds' : interpolation_bounds,
      'resolution' : interpolator.resolution,
      'grid' : grid.tolist()
   })

@aqi.route('/api/partitions')
def partitions():
   redis = get_redis()

   key = current_app.config['KEY_PREFIX'] + 'PT' + str(current_app.config['PARTITION']) + 'M-PARTITIONS'

   cursor = -1
   partitions = []
   while cursor!=0:
      if cursor<0:
         cursor = 0
      values = redis.zscan(key,cursor=cursor)
      cursor = values[0]
      for key,value in values[1]:
         key = key.decode('utf-8')
         partitions.append(key)

   return jsonify(partitions)

assets = Blueprint('aqi_assets',__name__)
@assets.route('/assets/<path:path>')
@gzipped
def send_asset(path):
   dir = current_app.config.get('ASSETS')
   if dir is None:
      pos = __file__.rfind('/')
      if pos < 0:
         dir = os.getcwd() + '/assets/'
      else:
         dir = __file__[:pos] + '/assets/'
   print(__file__)
   print(dir)
   return send_from_directory(dir, path)


def create_app(host='0.0.0.0',port=6379,password=None,prefix='AQI30-',partition=30,app=None):
   if app is None:
      app = Flask(__name__)
   app.register_blueprint(aqi)
   app.register_blueprint(assets)
   if 'REDIS_HOST' not in app.config:
      app.config['REDIS_HOST'] = host
   if 'REDIS_PORT' not in app.config:
      app.config['REDIS_PORT'] = port
   if 'REDIS_PASSWORD' not in app.config:
      app.config['REDIS_PASSWORD'] = password
   if 'KEY_PREFIX' not in app.config:
      app.config['KEY_PREFIX'] = prefix
   if 'PARTITION' not in app.config:
      app.config['PARTITION'] = partition
   return app

def main():
   argparser = argparse.ArgumentParser(description='Web')
   argparser.add_argument('--host',help='Redis host',default='0.0.0.0')
   argparser.add_argument('--port',help='Redis port',type=int,default=6379)
   argparser.add_argument('--password',help='Redis password')
   argparser.add_argument('--config',help='configuration file')
   argparser.add_argument('--key-prefix',help='The key prefix.',default='AQI30-')
   argparser.add_argument('--partition',help='The time partition (in minutes, must be a divisor of 60)',default=30,type=int)
   args = argparser.parse_args()

   if 60 % args.partition:
      print('The partition {} is not a divisor of 60'.format(args.partition))
      sys.exit(1)

   app = create_app(host=args.host,port=args.port,password=args.password,prefix=args.key_prefix,partition=args.partition)
   if args.config is not None:
      import os
      app.config.from_pyfile(os.path.abspath(args.config))
   app.run()

if __name__ == '__main__':
   main()
