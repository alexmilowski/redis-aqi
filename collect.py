import argparse
import requests
import datetime
import time
import json
import signal
import sys
import os

import boto3

def utc_now():
   return datetime.datetime.utcnow().isoformat()

def dump_storage(start,data):
   sys.stdout.write('\u001e')
   json.dump({'start': start.isoformat(), 'data' : data},sys.stdout)
   sys.stdout.write('\n')
   sys.stdout.flush()

def create_dir_action(dir,prefix='data-'):

   def dir_storage(start,data):
      name = prefix + start.isoformat() + '.json'
      with open(os.path.join(dir,name),'w') as output:
         json.dump(data,output)
   return dir_storage

def create_s3_storage_action(bucket_name,verbose=False,endpoint=None,key=None,secret=None,prefix='data-'):
   kwargs = {}
   if endpoint is not None:
      kwargs['endpoint_url'] = endpoint
   if key is not None:
      kwargs['aws_access_key_id'] = key
   if secret is not None:
      kwargs['aws_secret_access_key'] = secret
   if verbose:
      print("S3 endpoint configured:")
      print(kwargs)
   client = boto3.client(
      "s3",
      **kwargs
   )

   def s3_storage(start,data):

      key_name = prefix + start.isoformat() + '.json'

      body = json.dumps(data).encode('utf-8')

      if verbose:
         print("Storing data to "+key_name,flush=True)

      client.put_object(Bucket=bucket_name,Key=key_name,Body=body,ContentLength=len(body),ContentType='application/json;charset=utf-8')

      if verbose:
         print("Complete",flush=True)

   return s3_storage

class Collector:
   def __init__(self,url,interval=60,partition_interval=5*60,datetime_header='timestamp',verbose=False,store_action=dump_storage):
      self.url = url
      self.interval = interval
      self.partition_interval= partition_interval
      self.datetime_header = datetime_header
      self.collecting = False
      self.headers = None
      self.data = None
      self.verbose = verbose
      self.store_action = store_action

   def partition(self):
      if self.data is not None and len(self.data)>0:
         self.store()
      self.parition_start = datetime.datetime.utcnow()
      self.data = []

   def stop(self):
      self.collecting = False
      self.store()

   def collect(self):

      self.collecting = True

      self.partition()

      def pause():
         time.sleep(self.interval)

      while self.collecting:

         # check for a partition
         elapsed = datetime.datetime.utcnow() - self.parition_start
         if elapsed.total_seconds() >= self.partition_interval:
            self.partition()

         # request the data
         response = requests.get(self.url)
         if response.status_code!=200:
            print('({status}) {text}'.format(status=response.status_code,text=response.text),file=sys.stderr,flush=True)
            pause()
            continue

         try:
            current_data = response.json()
         except json.decoder.JSONDecodeError as e:
            print('{line}:{column} {msg}'.format(line=e.lineno,column=e.colno,msg=e.msg),file=sys.stderr)
            print(response.text,file=sys.stderr,flush=True)
            pause()
            continue

         timestamp = utc_now()
         if self.verbose:
            print('{timestamp} : {count}'.format(timestamp=timestamp,count=current_data.get('count',0)),flush=True)

         # store the headers
         if self.headers is None:
            self.headers = current_data['fields'].copy()
            self.headers.insert(0,self.datetime_header)

         if 'data' in current_data:
            # add the rows of data
            for row in current_data['data']:
               # add the timestamp
               row.insert(0,timestamp)
               self.data.append(row)

         # pause for the interval
         pause()

   def store(self):
      if self.data is None:
         return

      if self.headers is not None:
         self.data.insert(0,self.headers)

      self.store_action(self.parition_start,self.data)
      self.data = None

if __name__ == '__main__':

   argparser = argparse.ArgumentParser(description='collect-aq')
   argparser.add_argument('--verbose',help='Verbose output',action='store_true',default=False)
   argparser.add_argument('--interval',help='The collection interval (seconds)',type=int,default=60)
   argparser.add_argument('--partition',help='The data partition (in seconds)',type=int,default=5*60)
   argparser.add_argument('--align',help='Align time partitions',action='store_true',default=False)
   argparser.add_argument('--url',help='The base service url',default='https://www.purpleair.com/data.json')
   argparser.add_argument('--bounding-box',help='The bounding box (nwlat,nwlon,selat,selon)',default='37.80888750820881,-122.57097888976305,37.719593811785046,-122.32739139586647')
   argparser.add_argument('--bounding-box-parameters',help='The bounding box parameter names',default='nwlat,nwlng,selat,selng')
   argparser.add_argument('--fields',help='The fields to record',default='pm_0,pm_1,pm_2,pm_3,pm_4,pm_5,pm_6')
   argparser.add_argument('--datetime-header',help='The name of the datetime header column',default='timestamp')

   argparser.add_argument('--dir',help='The directory in which to store the data')

   argparser.add_argument('--s3-endpoint',help='The S3 endpoint url')
   argparser.add_argument('--s3-bucket',help='The S3 bucket name.')
   argparser.add_argument('--s3-key',help='The S3 Access Key')
   argparser.add_argument('--s3-secret',help='The S3 Secret')
   argparser.add_argument('--prefix',help='The prefix for the data files in the bucket.',default='data-')

   args = argparser.parse_args()

   if args.s3_bucket is not None and args.dir is not None:
      print('You cannot specify an S3 bucket and directory at the same time.',file=sys.stderr)
      sys.exit(1)

   url = args.url

   box_params = args.bounding_box_parameters.split(',')
   box = args.bounding_box.split(',')

   connector = '?'

   for param,value in zip(box_params,box):
      url += connector + param + '=' + value
      connector = '&'

   url += '&fields=' + args.fields

   store_action = dump_storage
   if args.s3_bucket is not None:
      store_action = create_s3_storage_action(args.s3_bucket,verbose=args.verbose,endpoint=args.s3_endpoint,key=args.s3_key,secret=args.s3_secret,prefix=args.prefix)

   if args.dir is not None:
      store_action = create_dir_action(args.dir,prefix=args.prefix)

   data_collector = Collector(url,interval=args.interval,partition_interval=args.partition,datetime_header=args.datetime_header,verbose=args.verbose,store_action=store_action)

   def interupt_handler(sig, frame):
      data_collector.stop()
      sys.exit(0)
   signal.signal(signal.SIGINT, interupt_handler)

   data_collector.collect()
