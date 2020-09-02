# redis-aqi
A demonstration of the geospatial features of Redis to interpolate an AQI (Air Quality Index) from sensor data.

This project provides a sample application that uses Redis as a database to
store geospatial air quality data (see [Using Redis](#using-redis)). The raw data from sensors is transformed into [AQI (Air Quality Index)](https://www.airnow.gov/aqi/aqi-basics/) measurements and stored as in geospatial partitions.

A simple Flask-based application (see [Demonstration](#demonstration)) creates a map-based interactive experience with the datetime and geospatial partitions of the data and displays an interpolated (estimated) surface of AQI measurements (see [Interpolation](#interpolation)).

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

Also, if you need to update the python script or parameters, you can use the --dry-run parameter to kubectl. For example, the script can be updated with:

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

## Interpolation

Interpolation of AQI values relies on having an atmospheric model for
the distribution of particulate matter that takes into account weather,
wind conditions, elevation, etc. Absent such a model, standard
interpolation methods such as [linear interpolation](https://en.wikipedia.org/wiki/Linear_interpolation) can be used as a gross estimation of the AQI
over a geospatial area.

The following example (from the Bay Area 2028-08-28) uses the krige exponential method of interpolation:

![Example interpolation of AQI from 2020-08-28](example-2020-08-28T13%3a30%3a00PT30M.png)

You can use a variety of method to interpolate a grid of AQI values from
the observed values. The python program [interpolate.py](interpolate.py)
provides an implementation basic linear, cubic, nearest, and krige-based
methods of interpolation as a library as well as a program.

You can try the interpolation on collected data by:

```
python interpolate.py url [url ...]
```

The options are:

 * --verbose

   enable verbose output
 * --size nn

   The grid mesh size (integer)
 * --resolution nn.nnn

   The grid resolution (float)
 * --index n

   The pm measurement to use - a value from 0 to 6
 * --method linear|cubic|nearest|krige-linear|krige-power|krige-gaussian|krige-spherical|krige-exponential|krige-hole-effect
 * --bounding-box' nwlat,nwlon,selat,selon

   The bounding box (quadrangle) for the interpolation

Note: You should only specify --size or --resolution but not both.

The library provides a function called `aqiFromPM` for calculating the AQI
from the PM value.

There is also a `AQIInterpolator` class that can be used directly and
provides the same functionality as the command-line program.

## Using Redis

More to come ...

## Demonstration

A simple Flask-based web application will provide a map-based interactive experience with the data. You can run the application against a local Redis instance:

```
python app.py
```

You can connect to a Redis database with the following parameters:

 * --host ip

   The Redis host address
 * --port nnn

   The Redis port

 * --password password

   The Redis password

The data is stored in Redis by ISO 8601 dateTime labeled partitions. You can provide alternate key prefix and partition period information by:

 * --key-prefix prefix
 * --partition nnn

Note: The partition time is in minutes.

Alternatively, all of the above settings can be set in the Flask configuration file and specified by the --config option. The keys are:

 * REDIS_HOST
 * REDIS_PORT
 * REDIS_PASSWORD
 * KEY_PREFIX
 * PARTITION
