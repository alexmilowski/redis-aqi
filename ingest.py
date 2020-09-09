import redis
import sys
import os
import requests
import json
import argparse
from datetime import datetime, date

from interpolate import aqiFromPM

def ingest(client, data, box=None, partition=30,prefix='AQI30-',verbose=False):
   # ['timestamp', 'ID', 'age', 'pm_0', 'pm_1', 'pm_2', 'pm_3', 'pm_4', 'pm_5', 'pm_6', 'conf', 'Type', 'Label', 'Lat', 'Lon', 'isOwner', 'Flags', 'CH']
   # print(data[0])
   duration = 'PT' + str(partition) + 'M'
   partiton_set = prefix + duration
   last_partition_no = -1
   last_hour = -1
   count = 0
   for row in data[1:]:
      # We must have a lat/lon
      if row[13] is None or row[14] is None:
         continue
      # The age should be less than 30 minutes and the sensor must be outdoor (0)
      if row[2]>30 or row[11]!=0:
         continue

      pm = [float(row[3 + index]) if row[3 + index] is not None else 0.0 for index in range(7)]
      if sum(pm) == 0:
         # no measurements - bad row
         continue

      timestamp = datetime.fromisoformat(row[0])
      lat, lon = float(row[13]), float(row[14])
      #aqi = aqiFromPM(float(row[3 + index]))

      partition_no = timestamp.minute // partition
      partition_start = datetime(timestamp.year,timestamp.month,timestamp.day,timestamp.hour,partition_no * partition,tzinfo=timestamp.tzinfo)
      partition_duration = partition_start.isoformat() + duration
      offset = timestamp.minute % partition
      key = prefix + partition_duration

      # prefix + partition start dateTime + duration (e.g., AQI30-2020-08-25T16:00:00PT30M)
      client.geoadd(key,lon,lat,str(row[1]) + '@' + str(offset) + ',' + ','.join(map(lambda n : str(round(n,2)),pm)))
      if last_hour!=partition_start.hour or last_partition_no != partition_no:
         # prefix + duration (e.g., AQI30-PT30M)
         score = partition_start.year*10**8 + partition_start.month*10**6 + partition_start.day*10**4 + partition_start.hour*60 + partition_start.minute
         client.zadd(partiton_set,{key : score})
      last_partition_no = partition_no
      last_hour = partition_start.hour
      count += 1
      if verbose:
         print(str(count),end='')
         print('\r',end='')
   if verbose:
      print()


def ingest_urls(source,client,box=None, partition=30,prefix='AQI30-',verbose=False):
   if type(source)==str:
      def from_string():
         for url in str.split('\n'):
            if len(url)>0:
               yield url.strip()
      urls = from_string()
   else:
      def from_file():
         for url in source:
            url = url.strip()
            if len(url)>0:
               yield url
      urls = from_file()

   for url in urls:
      if verbose:
         print(url)
      resp = requests.get(url)
      if resp.status_code==200:
         ingest(client,resp.json(),box=box,partition=partition,prefix=prefix,verbose=verbose)
      else:
         print('Error getting {}, status={}'.format(spec,resp.status_code))
         print(resp.text)
         sys.exit(1)


if __name__ == '__main__':

   argparser = argparse.ArgumentParser(description='collect-aq')
   argparser.add_argument('--host',help='Redis host',default='0.0.0.0')
   argparser.add_argument('--port',help='Redis port',type=int,default=6379)
   argparser.add_argument('--password',help='Redis password')
   argparser.add_argument('--verbose',help='Verbose output',action='store_true',default=False)
   argparser.add_argument('--index',help='The PM measurement index',choices=[0,1,2,3,4,5,6],default=2)
   argparser.add_argument('--key-prefix',help='The key prefix.',default='AQI30-')
   argparser.add_argument('--partition',help='The time partition (in minutes, must be a divisor of 60)',default=30,type=int)
   argparser.add_argument('--bounding-box',help='The bounding box (nwlat,nwlon,selat,selon)')
   argparser.add_argument('--urls',help='Indicates the source is a list of urls',action='store_true',default=False)
   argparser.add_argument('source',help='A list of files or urls of data to ingest (or - for stdin)',nargs='+')

   args = argparser.parse_args()

   client = redis.Redis(host=args.host,port=args.port,password=args.password)

   box = None
   if args.bounding_box is not None:
      try:
         box = map(float,args.bounding_box.split(','))
      except ValueError:
         print('Invalid number in box specification: '+args.bounding_box,file=sys.stderr)
         sys.exit(1)
      if len(box)!=4:
         print('Incorrect number of points in box specification: '+args.bounding_box,file=sys.stderr)
         sys.exit(1)

   if 60 % args.partition:
      print('The partition {} is not a divisor of 60'.format(args.partition))
      sys.exit(1)

   sources = args.source
   if args.source[0]=='-':
      if len(args.source)>1:
         print('stdin (-) must be by itself')
         sys.exit(1)
      sources = [sys.stdin]

   for source in sources:
      if type(source)==str:
         if os.path.isfile(spec):
            with open(source,'r') as input:
               if args.urls:
                  ingest_urls(input,client,box=box,partition=args.partition,prefix=args.key_prefix,verbose=args.verbose)
               else:
                  data = json.load(input)
                  ingest(client,data,box=box,partition=args.partition,prefix=args.key_prefix,verbose=args.verbose)
         else:
            resp = requests.get(source)
            if resp.status_code==200:
               if args.urls:
                  ingest_urls(resp.text,client,box=box,partition=args.partition,prefix=args.key_prefix,verbose=args.verbose)
               else:
                  ingest(client,resp.json(),box=box,partition=args.partition,prefix=args.key_prefix,verbose=args.verbose)
            else:
               print('Error getting {}, status={}'.format(spec,resp.status_code))
               print(resp.text)
               sys.exit(1)
      else:
         if args.urls:
            ingest_urls(source,client,box=box,partition=args.partition,prefix=args.key_prefix)
         else:
            data = json.load(source)
            ingest(client,data,box=box,partition=args.partition,prefix=args.key_prefix)
