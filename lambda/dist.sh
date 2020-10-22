#!/bin/bash
cd $1
rm -rf dist
mkdir dist
cd dist
virtualenv env
source env/bin/activate
pip install -r ../requirements.txt
mkdir package
cp -r env/lib/python3.8/site-packages/* package
cp -r /flask-serverless/flask_serverless package
cp ../production.py package
cp /redis-aqi/app.py package
cp /redis-aqi/geo.py package
cp /redis-aqi/interpolate.py package
cp /redis-aqi/ingest.py package
cp -r /redis-aqi/templates package
cp -r /redis-aqi/assets package
find package -name __pycache__ -exec rm -rf {} \;
rm -f ../lambda.zip
cd package
zip -r ../../lambda.zip .
