# redis-aqi
A demonstration of the geospatial features of Redis to interpolate an AQI (Air Quality Index) from sensor data.

# Data sources

[PurpleAir sells](https://www.purpleair.com) air quality sensors that measure
particulate matter in the air and upload that data to a data repository. They
provide access to this [aggregated data via an API](https://docs.google.com/document/d/15ijz94dXJ-YAZLi9iZ_RaBwrZ4KtYeCy08goGBwnbCU/edit#heading=h.2tzq9j55gsj6).

At its simplest, the API returns a list of sensor readings for a given
bounding box defined by a pair of coordinate parameters defining the north west
and south east corners of the bounds. The resulting data contains the current
sensor data with rolling averages for the particulate matter readings.

PurpleAir provides documentation for how to turn the PM readings into an [AQI (Air Quality Index)](https://www.airnow.gov/aqi/aqi-basics/)
measure.

# Setup

You can create a python environment with all the required packages by:

```
pip install -r requirements.txt
```

# Collecting Data

The python program [collect.py](collect.py) provides a simple command line
interface to data collection that can optional poll an regular intervals and
collect the data from the API. This data is aggregated by the program and can
be stored in a variety of ways (e.g., in S3-compatible cloud storage).

This program can be run as:

```
# collect for the bay area every 5 minutes and partition by 30 minutes
python collect.py --bounding-box 38.41646632263371,-124.02669995117195,36.98663820370443,-120.12930004882817  --interval 300 --partition 1800 --s3-bucket purpleair
```

some common options are:

 * --bounding-box nwlat,nwlon,selat,selon

   The bounding box for collection; floating poing numbers representing the north west and south east corners of the quadrangle
 * --internal seconds

   The collection interval in seconds
 * --partition seconds

   The elapsed time in seconds at which to partition the data for storage
 * --prefix value

     The data file prefix
 * --s3-endpoint url

   A non-AWS endpoint for S3 (e.g., https://storage.googleapis.com)
 * --s3-bucket name

   The S3 bucket name for storage
 * --s3-key aws_access_key_id

   The AWS access key

 * --s3-secret aws_secret_access_key

   The AWS secret access key

Any boto3 authentication method can be used (e.g., the AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables).

## Data storage

The collect.py program will retrieve data from the API at the interval you
specify. It will aggregate the collected data until the partition time
limit has been reached and then store the tabular data as a JSON artifact. By
default, the data is sent to stdout in [JSON Text Sequences](https://tools.ietf.org/html/rfc7464).

You can store data in files by specifying the --dir parameter with a directory name.

You can store data in an S3 bucket by specifying the --s3-bucket parameter with
a bucket name.

In each case, the file name generated is the prefix appended with the ISO 8601
date and time format and suffixed with .json extension. For example, `data-2020-09-02T00:25:23.596826.json`.

## Using a Kubernetes job to collect data

A long-running Kubernetes job can be used to collect data. The job specification is located in [collection.yaml](collection.yaml).

### Setup

Create the S3 credentials in a secret:

```
kubectl create secret generic s3 --from-literal=access-key-id=... "--from-literal=secret-access-key=..."
```

Store the collection script in a configmap:
```
kubectl create configmap collect --from-file=collect.py=collect.py
```

Setup the collection parameters
```
kubectl create configmap parameters \
--from-literal=box=38.41646632263371,-124.02669995117195,36.98663820370443,-120.12930004882817 \
--from-literal=endpoint=https://storage.googleapis.com \
--from-literal=bucket=purpleair \
--from-literal=interval=300 \
--from-literal=partition=1800
```

Note: Amazon S3 endpoints can be [found here](https://docs.aws.amazon.com/general/latest/gr/s3.html) or
you can omit the --endpoint parameter from the [collection.yaml](collection.yaml) job specification.

If you need to update the python script or parameters, you can use the --dry-run parameter to kubectl. For example, the script can be updated with:

```
kubectl create configmap collect --from-file=collect.py=collect.py --dry-run -o yaml | kubectl apply -f -
```

### Submit the Job

```
kubectl apply -f collection.yaml
```

### Monitoring

You can monitor the progress at:

```
kubectl logs job/purpeair-collection
```
