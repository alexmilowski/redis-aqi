import argparse
import yaml
import sys

def child(container,name):
   return container.get(name) if container is not None else None

if __name__ == '__main__':

   argparser = argparse.ArgumentParser(description='job')
   argparser.add_argument('--index',help='The PM measurement index (list of integers)')
   argparser.add_argument('--precision',help='Round the measurements to the precision',type=int)
   argparser.add_argument('--partition',help='The time partition (in minutes, must be a divisor of 60)',default=30,type=int)
   argparser.add_argument('--bucket-url',help='The bucket url prefix')
   argparser.add_argument('--endpoint',help='The endpoint url')
   argparser.add_argument('--bucket',help='The bucket name')
   argparser.add_argument('--type',help='The kind of ingest action',choices=['data','urls','now', 'at'],default='data')
   argparser.add_argument('--template',help='The job template.',default='ingest.yaml')
   argparser.add_argument('--container',help='The container',default='ingest')
   argparser.add_argument('--name',help='The job-name',default='ingest')
   argparser.add_argument('source',help='A list of files or urls of data to ingest (or - for stdin)',nargs='*')

   args = argparser.parse_args()

   if 60 % args.partition:
      print('The partition {} is not a divisor of 60'.format(args.partition))
      sys.exit(1)

   with open(args.template,'r') as template:
      job = yaml.load(template,Loader=yaml.Loader);

   metadata = child(job,'metadata')
   metadata['name'] = args.name

   if len(args.source)==1 and args.source[0]=='-':
      args.source = [l.strip() for l in sys.stdin.readlines()]

   containers = child(child(child(child(job,'spec'),'template'),'spec'),'containers')
   for container in containers:
      if container.get('name','')==args.container:
         for index,env in enumerate(container.get('env',[])):
            name = env.get('name','')
            if args.index is not None and name=='INDEX':
               env['value'] = args.index
            if args.precision is not None and name=='PRECISION':
               env['value'] = str(args.precision)
            if args.bucket_url is not None and name=='BUCKET_URL':
               env['value'] = args.bucket_url
            if args.endpoint is not None and name=='ENDPOINT':
               env['value'] = args.endpoint
            if args.bucket is not None and name=='BUCKET':
               env['value'] = args.bucket
            if args.type is not None and name=='TYPE':
               env['value'] = args.type
            if args.source is not None and name=='ARGS':
               env['value'] = ' '.join(args.source)

   print(yaml.safe_dump(job,indent=2,width=4096))
