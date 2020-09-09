
import boto3
from datetime import date, timedelta, datetime
import argparse


def get_keys_by_day(client, bucket, day, at_hour=None, prefix='data-'):

   key_prefix = prefix + day.isoformat()
   resp = client.list_objects(Bucket=bucket,Prefix=key_prefix)
   if 'Contents' in resp:
      for obj in resp['Contents']:
         key = obj['Key']
         if at_hour is not None:
            partition = datetime.fromisoformat(key[len(prefix):-5])
            if partition.hour < at_hour:
               continue
         yield key

# https://storage.googleapis.com/purpleair/data-2020-08-24T23%3A41%3A33.958894.json


if __name__ == '__main__':

   argparser = argparse.ArgumentParser(description='enumerate')
   argparser.add_argument('--verbose',help='Verbose output',action='store_true',default=False)
   argparser.add_argument('--days',help='The number of days to enumerate',type=int,default=-1)
   argparser.add_argument('--at-hour',help='The hour to start at',type=int)
   argparser.add_argument('--start',help='A start date')
   argparser.add_argument('--s3-endpoint',help='The S3 endpoint url')
   argparser.add_argument('--s3-key',help='The S3 Access Key')
   argparser.add_argument('--s3-secret',help='The S3 Secret')
   argparser.add_argument('--prefix',help='The prefix for the data files in the bucket.',default='data-')
   argparser.add_argument('--format',help='A URL template for the output, keys=bucket,key')
   argparser.add_argument('bucket',help='The bucket name')

   args = argparser.parse_args()

   s3_args = {}
   if args.s3_endpoint is not None:
      s3_args['endpoint_url'] = args.s3_endpoint
   if args.s3_key is not None:
      s3_args['aws_access_key_id'] = args.s3_key
   if args.s3_secret is not None:
      s3_args['aws_secret_access_key'] = args.s3_secret

   client = boto3.client(
      "s3",
      **s3_args
   )

   stop_day = date.fromtimestamp(datetime.utcnow().timestamp())

   day = date.fromisoformat(args.start) if args.start is not None else stop_day
   one_day = timedelta(days=1)

   count = args.days
   at_hour = args.at_hour
   while count<0 or count>0:
      for key in get_keys_by_day(client,args.bucket,day,at_hour=at_hour,prefix=args.prefix):
         if args.format is not None:
            print(args.format.format(bucket=args.bucket,key=key))
         else:
            print(key)
      day = day + one_day
      if count > 0:
         count -= 1
      if day > stop_day:
         count = 0
      at_hour = None
