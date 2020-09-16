import redis
import sys
import os
import requests
import json
import argparse
from datetime import datetime, date, timedelta

# support for python 3.6
def fromisoformat(value):
   if hasattr(datetime,'fromisoformat'):
      return datetime.fromisoformat(value)
   else:
      if value.find('.')<0:
         return datetime.strptime(value,'%Y-%m-%dT%H:%M:%S')
      else:
         return datetime.strptime(value,'%Y-%m-%dT%H:%M:%S.%f')

def datetime_score(value):
   return value.year*10**8 + value.month*10**6 + value.day*10**4 + value.hour*60 + value.minute

def ingest(client, data, precision=None, indices=None,box=None, partition=30,prefix='AQI30-',verbose=False):
   # pm_0 : now
   # pm_1 : 10M
   # pm_2 : 30M
   # pm_3 : 1H
   # pm_4 : 6H
   # pm_5 : 1D
   # pm_6 : 7D
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

      if indices is not None:
         pm = [pm[i] for i in indices]

      if precision is not None:
         if precision==0:
            pm = map(round,pm)
         else:
            pm = map(lambda v : round(v,precision),pm)

      timestamp = fromisoformat(row[0])
      lat, lon = float(row[13]), float(row[14])

      partition_no = timestamp.minute // partition
      partition_start = datetime(timestamp.year,timestamp.month,timestamp.day,timestamp.hour,partition_no * partition,tzinfo=timestamp.tzinfo)
      partition_duration = partition_start.isoformat() + duration
      offset = timestamp.minute % partition
      key = prefix + partition_duration

      # prefix + partition start dateTime + duration (e.g., AQI30-2020-08-25T16:00:00PT30M)
      client.geoadd(key,lon,lat,str(row[1]) + '@' + str(offset) + ',' + ','.join(map(str,pm)))
      if last_hour!=partition_start.hour or last_partition_no != partition_no:
         # prefix + duration (e.g., AQI30-PT30M)
         score = datetime_score(partition_start)
         client.zadd(partiton_set,{key : score})
      last_partition_no = partition_no
      last_hour = partition_start.hour
      count += 1
      if verbose:
         print(str(count),end='')
         print('\r',end='')
   if verbose:
      print()


def ingest_urls(source,client,precision=None,indices=None,box=None, partition=30,prefix='AQI30-',verbose=False):
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
         ingest(client,resp.json(),precision=precision,indices=indices,box=box,partition=partition,prefix=prefix,verbose=verbose)
      else:
         print('Error getting {}, status={}'.format(spec,resp.status_code))
         print(resp.text)
         sys.exit(1)

def date_range(spec,partition=30):
   parts = spec.split(',')
   if len(parts)==1:
      yield fromisoformat(parts[0])
      return
   elif len(parts)==2:
      current_dt = fromisoformat(parts[0])
      to_dt = fromisoformat(parts[1])
   elif len(parts)==3:
      current_dt = fromisoformat(parts[0])
      to_dt = fromisoformat(parts[1])
      partition = int(parts[2])
   else:
      raise ValueError(spec+' is not a valid date rate')

   if current_dt > to_dt:
      raise ValueError('End date is before start.')

   while current_dt <= to_dt:
      yield current_dt
      current_dt += timedelta(minutes=partition)


if __name__ == '__main__':

   argparser = argparse.ArgumentParser(description='ingest')
   argparser.add_argument('--host',help='Redis host',default='0.0.0.0')
   argparser.add_argument('--port',help='Redis port',type=int,default=6379)
   argparser.add_argument('--password',help='Redis password')
   argparser.add_argument('--verbose',help='Verbose output',action='store_true',default=False)
   argparser.add_argument('--confirm',help='Confirm partitions',action='store_true',default=False)
   argparser.add_argument('--index',help='The PM measurement index (list of integers)')
   argparser.add_argument('--precision',help='Round the measurements to the precision',type=int)
   argparser.add_argument('--key-prefix',help='The key prefix.',default='AQI30-')
   argparser.add_argument('--bucket-url',help='The bucket url prefix')
   argparser.add_argument('--partition',help='The time partition (in minutes, must be a divisor of 60)',default=30,type=int)
   argparser.add_argument('--bounding-box',help='The bounding box (nwlat,nwlon,selat,selon)')
   argparser.add_argument('--type',help='The kind of ingest action',choices=['data','urls','now', 'at'],default='data')
   argparser.add_argument('--ignore-not-found',help='Ignore not found errors',action='store_true',default=False)
   argparser.add_argument('source',help='A list of files or urls of data to ingest (or - for stdin)',nargs='*')

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
   if len(args.source)==0 or (len(args.source)==1 and args.source[0]=='-'):
      sources = [sys.stdin]

   indices = None
   if args.index is not None and args.index != "all":
      try:
         indices = list(map(int,args.index.split(',')))
         for value in indices:
            if value<0 or value>6:
               raise ValueError('Index {} is not in the range [0,6]'.format(value))
      except ValueError as ex:
         print('Invalid indicies list: '+args.index)
         sys.exit(1)

   kwargs = {
     'precision' : args.precision,
     'indices' : indices,
     'box' : box,
     'partition' : args.partition,
     'prefix' : args.key_prefix,
     'verbose' : args.verbose
   }

   if args.type=='now':
      if args.bucket_url is None:
         print('You must provide a base URL for the bucket.',file=sys.stderr)
         sys.exit(1)

      timestamp = datetime.utcnow()
      partition_no = timestamp.minute // args.partition
      partition_start = datetime(timestamp.year,timestamp.month,timestamp.day,timestamp.hour,partition_no * args.partition,tzinfo=timestamp.tzinfo)
      prev_timestamp = timestamp - timedelta(minutes=args.partition)
      prev_partition_no = prev_timestamp.minute // args.partition
      prev_partition_start = datetime(prev_timestamp.year,prev_timestamp.month,prev_timestamp.day,prev_timestamp.hour,prev_partition_no * args.partition,tzinfo=prev_timestamp.tzinfo)
      sources = [args.bucket_url + partition_start.isoformat() + '.json', args.bucket_url + prev_partition_start.isoformat() + '.json']
      args.type = 'data'

   if args.type=='at':

      if args.bucket_url is None:
         print('You must provide a base URL for the bucket.',file=sys.stderr)
         sys.exit(1)

      sources = []
      for item in args.source:
         sources += map(lambda timestamp : args.bucket_url + timestamp.isoformat() + '.json', date_range(item))
      args.type = 'data'


   if args.type=='data':
      for source in sources:
         if args.verbose or args.confirm:
            print(source,flush=True)
         if type(source)==str:
            if os.path.isfile(source):
               with open(source,'r') as input:
                  data = json.load(input)
                  ingest(client,data,**kwargs)
            else:
               resp = requests.get(source)
               if resp.status_code==200:
                  ingest(client,resp.json(),**kwargs)
               else:
                  if args.ignore_not_found and resp.status_code==404:
                     print('{} not found'.format(source),file=sys.stderr)
                     continue
                  print('Error getting {}, status={}'.format(source,resp.status_code))
                  print(resp.text)
                  sys.exit(1)
         else:
            data = json.load(source)
            ingest(client,data,**kwargs)

   elif args.type=='urls':
      for source in sources:
         if args.verbose or args.confirm:
            print(source,flush=True)
         if type(source)==str:
            if os.path.isfile(source):
               with open(source,'r') as input:
                  ingest_urls(input,client,**kwargs)
            else:
               resp = requests.get(source)
               if resp.status_code==200:
                  ingest_urls(resp.text,client,**kwargs)
               else:
                  if args.ignore_not_found and resp.status_code==404:
                     print('{} not found'.format(source),file=sys.stderr)
                     continue
                  print('Error getting {}, status={}'.format(source,resp.status_code))
                  print(resp.text)
                  sys.exit(1)
         else:
            ingest_urls(source,client,**kwargs)
