import os
import sys

from flask import Flask
from flask import request, current_app, Blueprint, send_from_directory, render_template, after_this_request, jsonify, g, abort

import redis

import gzip
import functools
import argparse

from geo import query_circle, query_quadrangle
from geo import quadrangle_for_sequence_number
from geo import is_valid_datetime_partition

from interpolate import loader, AQIInterpolator, aqiFromPM
from ingest import datetime_score
from datetime import datetime
from time import time

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

@aqi.route('/api/q/<size>/n/<sequence_number>/<datetime_partition>/')
@aqi.route('/api/q/<size>/n/<sequence_number>/<datetime_partition>')
@gzipped
def quadrandle(size,sequence_number,datetime_partition):
   client = get_redis()

   partition_start = datetime.fromisoformat(datetime_partition)

   partition = current_app.config.get('PARTITION',30)
   if not is_valid_datetime_partition(partition,partition_start):
      return jsonify({'error':'Invalid datetime partition, partitions muse end every {partition} minutes: {t}'.format(partition=partition,t=datetime_partition)}),400

   try:
      size = float(size)
   except ValueError as e:
      return jsonify({'error':'Invalid partition size: '+str(e)}),400

   try:
      sequence_number = int(sequence_number)
   except ValueError as e:
      return jsonify({'error':'Invalid sequence number: '+str(e)}),400

   nw, se = quadrangle_for_sequence_number(size,sequence_number)

   key = current_app.config['KEY_PREFIX'] + datetime_partition + 'PT' + str(partition) + 'M'

   result = query_quadrangle(client,key,nw,se)

   data = []
   for key, pos in result:

      sensor = key.decode('utf-8').split(',')
      id, minute = sensor[0].split('@')
      minute = int(minute)
      readings = list(map(float,sensor[1:]))
      data.append([id,minute] + [pos[0],pos[1]] + readings)

   return jsonify(data)

@aqi.route('/api/interpolate',methods=['POST'])
@gzipped
def interpolate_region():
   client = get_redis()

   data = request.json

   size = data.get('size',0.5)

   if 'bounds' not in data:
      return jsonify({'error':'Missing bounds of region.'}),400



   bounds = data.get('bounds')

   partition_start = datetime.fromisoformat(datetime_partition)

   partition = current_app.config.get('PARTITION',30)
   if not is_valid_datetime_partition(partition,partition_start):
      return jsonify({'error':'Invalid datetime partition, partitions muse end every {partition} minutes: {t}'.format(partition=partition,t=datetime_partition)}),400

   try:
      size = float(size)
   except ValueError as e:
      return jsonify({'error':'Invalid partition size: '+str(e)}),400

   try:
      sequence_number = int(sequence_number)
   except ValueError as e:
      return jsonify({'error':'Invalid sequence number: '+str(e)}),400

   nw, se = quadrangle_for_sequence_number(size,sequence_number)

   key = current_app.config['KEY_PREFIX'] + datetime_partition + 'PT' + str(partition) + 'M'

   result = query_quadrangle(client,key,nw,se)

   data = []
   for key, pos in result:

      sensor = key.decode('utf-8').split(',')
      id, minute = sensor[0].split('@')
      minute = int(minute)
      readings = list(map(float,sensor[1:]))
      data.append([id,minute] + [pos[0],pos[1]] + readings)

   return jsonify(data)


@aqi.route('/api/partition/<partition_set>/')
@aqi.route('/api/partition/<partition_set>')
def partition(partition_set):
   client = get_redis()

   key = current_app.config['KEY_PREFIX'] + partition_set

   try:
      lat = float(request.args.get('lat')) if 'lat' in request.args else None
      lon = float(request.args.get('lon')) if 'lon' in request.args else None
      radius = float(request.args.get('radius')) if 'radius' in request.args else None
      unit = request.args.get('unit')

      nwlat = float(request.args.get('nwlat')) if 'nwlat' in request.args else None
      nwlon = float(request.args.get('nwlon')) if 'nwlon' in request.args else None
      selat = float(request.args.get('selat')) if 'selat' in request.args else None
      selon = float(request.args.get('selon')) if 'selon' in request.args else None
   except ValueError as e:
      return jsonify({'error':'Invalid parameter value: '+str(e)}),400



   bounds = None

   if None in [nwlat,nwlon,selat,selon]:
      return jsonify({'error': 'The bounds of the quadrangle are not completely specified. All of nwlat, nwlon, selat, and selon must be specified.'}), 400

   if unit is None:
      unit = 'km'

   if nwlat is not None and \
      nwlon is not None and \
      selat is not None and \
      selon is not None:

      result = query_quadrangle(client,key,(nwlat,nwlon),(selat,selon))

   else:

      if None in [lat,lon,radius]:
         return jsonify({'error': 'The bounds of the circle are not completely specified. All of lat, lon, and radius must be specified.'}), 400

      result = query_circle(client,key,(lat,lon),radius,unit=unit)

   data = []
   for key, pos in result:

      sensor = key.decode('utf-8').split(',')
      id, minute = sensor[0].split('@')
      minute = int(minute)
      readings = list(map(float,sensor[1:]))
      data.append([id,minute] + [pos[0],pos[1]] + readings)

   return jsonify(data)

@aqi.route('/api/partition/<partition_set>/interpolate')
def interpolate(partition_set):
   client = get_redis()

   #bayarea = [38.41646632263371,-124.02669995117195,36.98663820370443,-120.12930004882817]

   try:
      resolution = float(request.args.get('resolution')) if 'resolution' in request.args else 0.025
      index = int(request.args.get('index')) if 'index' in request.args else 0
      nwlat = float(request.args.get('nwlat')) if 'nwlat' in request.args else None
      nwlon = float(request.args.get('nwlon')) if 'nwlon' in request.args else None
      selat = float(request.args.get('selat')) if 'selat' in request.args else None
      selon = float(request.args.get('selon')) if 'selon' in request.args else None
   except ValueError as e:
      return jsonify({'error':'Invalid parameter value: '+str(e)}),400

   method = request.args.get('method','linear')


   if None in [nwlat,nwlon,selat,selon]:
      return jsonify({'error': 'The bounds of the quadrangle are not completely specified. All of nwlat, nwlon, selat, and selon must be specified.'}), 400

   lat_size = abs(nwlat - selat)
   lon_size = abs(nwlon - selon)
   scale = 0
   if lon_size<0.5:
      scale = 0.5/lon_size/2

   interpolation_bounds = [nwlat + lat_size*scale, nwlon - lon_size*scale, selat - lat_size*scale, selon + lon_size*scale]

   key = current_app.config['KEY_PREFIX'] + partition_set

   result = query_quadrangle(client,key,(interpolation_bounds[0],interpolation_bounds[1]),(interpolation_bounds[2],interpolation_bounds[3]))

   start = time();
   count = 0

   interpolator = AQIInterpolator(interpolation_bounds,resolution=resolution)
   for key, pos in result:
      sensor = key.decode('utf-8').split(',')
      # pm_0 at position 1
      pm = float(sensor[1+index])
      interpolator.add(pos[0],pos[1],[aqiFromPM(pm)])
      count += 1

   loaded = time();
   print('Loaded: '+str(loaded-start))

   if count==0:
      return jsonify({
         'bounds' : interpolation_bounds,
         'grid' : []
      })

   grid = interpolator.generate_grid(method=method,index=0)
   done = time();
   print('Interpolation: '+str(done-loaded))
   return jsonify({
      'bounds' : interpolation_bounds,
      'resolution' : interpolator.resolution,
      'grid' : grid.tolist()
   })

@aqi.route('/api/partitions')
def partitions():
   redis = get_redis()

   start = request.args.get('start')
   end = request.args.get('end')

   key = current_app.config['KEY_PREFIX'] + 'PT' + str(current_app.config['PARTITION']) + 'M'

   first = redis.zrange(key,0,0)
   last = redis.zrevrange(key,0,0)

   prefix_len = len(current_app.config['KEY_PREFIX'])

   if len(first)==0:
      return jsonify({})

   first = first[0].decode('utf-8')
   first_datetime = first[prefix_len:first.rfind('PT')]
   last = last[0].decode('utf-8')
   last_datetime = last[prefix_len:last.rfind('PT')]

   partition_info = {'duration' : 'PT' + str(current_app.config['PARTITION']) + 'M', 'first': {'at': first_datetime, 'partition':first}, 'last': {'at': last_datetime, 'partition':last}}
   if start is None and end is None:
      return jsonify(partition_info)

   if start is None:
      start = first_datetime


   if start.find('T')<0:
      start += 'T00:00:00'

   if end is not None and end.find('T')<0:
      end += 'T23:59:59'

   start = datetime.fromisoformat(start)

   if end is None:
      timestamp = datetime.utcnow()
      partition_no = timestamp.minute // current_app.config['PARTITION']
      end = datetime(timestamp.year,timestamp.month,timestamp.day,timestamp.hour,partition_no * current_app.config['PARTITION'],tzinfo=timestamp.tzinfo)
   else:
      end = datetime.fromisoformat(end)

   start_score = datetime_score(start)
   end_score = datetime_score(end)

   partitions = list(map(lambda v : v.decode('utf-8')[prefix_len:],redis.zrangebyscore(key,start_score,end_score)))

   partition_info['partitions'] = partitions
   return jsonify(partition_info)


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
   return send_from_directory(dir, path)

def from_env(name,default_value,dtype=str):
   return dtype(os.environ[name]) if name in os.environ else default_value

def create_app(host='0.0.0.0',port=6379,password=None,prefix='AQI30-',partition=30,app=None):
   app = Flask(__name__)
   if 'AQI_CONF' in os.environ:
      app.config.from_envvar('AQI_CONF')
   app.register_blueprint(aqi)
   app.register_blueprint(assets)
   if 'REDIS_HOST' not in app.config:
      app.config['REDIS_HOST'] = from_env('REDIS_HOST',host)
   if 'REDIS_PORT' not in app.config:
      app.config['REDIS_PORT'] = from_env('REDIS_PORT',port,dtype=int)
   if 'REDIS_PASSWORD' not in app.config:
      app.config['REDIS_PASSWORD'] = from_env('REDIS_PASSWORD',password)
   if 'KEY_PREFIX' not in app.config:
      app.config['KEY_PREFIX'] = from_env('KEY_PREFIX',prefix)
   if 'PARTITION' not in app.config:
      app.config['PARTITION'] = from_env('PARTITION',partition)
   return app

class Config(object):
   DEBUG=True
   REDIS_HOST = from_env('REDIS_HOST','0.0.0.0')
   REDIS_PORT = from_env('REDIS_PORT',6379,dtype=int)
   REDIS_PASSWORD = from_env('REDIS_PASSWORD',None)
   KEY_PREFIX = from_env('KEY_PREFIX','AQI30-')
   PARTITION = from_env('PARTITION',30)

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
