# redis-aqi

This project provides a demonstration of the use of the geospatial features of Redis
for the purpose store air quality sensor readings and provides a sample
Web application that can AQI (Air Quality Index) measurements over a map.

The raw data is collected from air quality sensors (see [Data sources](#data-sources))
and is transformed into [AQI (Air Quality Index)](https://www.airnow.gov/aqi/aqi-basics/)
measurements and stored as in geospatial partitions.

The demonstration application is a simple Flask-based application
that creates a map-based interactive experience with the date/time and geospatial
partitions of the data which displays an interpolated (estimated) surface
of AQI measurements (see [Interpolation](#interpolation)).

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

# Collecting dData

The python program [collect.py](collect.py) provides a simple command line
interface to data collection that can poll at regular intervals and
collect the data from the API. This data is aggregated by the program and can
be stored in a variety of ways (e.g., in an S3-compatible object storage).

## Running data collection

This program can be run as:

```
# collect for the bay area every 5 minutes and partition by 30 minutes
python collect.py --bounding-box 38.41646632263371,-124.02669995117195,36.98663820370443,-120.12930004882817  --interval 300 --partition 30 --s3-bucket yourbuckethere
```

some common options are:

 * --bounding-box nwlat,nwlon,selat,selon

   The bounding box for collection; floating poing numbers representing the north west and south east corners of the quadrangle
 * --internal seconds

   The collection interval in seconds
 * --partition minutes

   The elapsed time in seconds at which to partition the data for storage
 * --prefix value

     The data file prefix
 * --s3-endpoint url

   A endpoint for the S3 protocol (e.g., https://storage.googleapis.com or [AWS endpoints](https://docs.aws.amazon.com/general/latest/gr/s3.html))
 * --s3-bucket name

   The S3 bucket name for storage
 * --s3-key aws_access_key_id

   The AWS access key

 * --s3-secret aws_secret_access_key

   The AWS secret access key

Any boto3 authentication method can be used (e.g., the AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables) instead of the command-line parameters.

## Where data is stored

The collect.py program retrieves data from the API at the interval you
specify. It will aggregate the collected data until the partition time
limit has been reached and then store the tabular data as a JSON artifact. By
default, the data is sent to stdout in [JSON Text Sequences](https://tools.ietf.org/html/rfc7464).

You can store data in files by specifying the --dir parameter with a directory name.

You can store data in an S3 bucket by specifying the --s3-bucket parameter with
a bucket name.

In each case, the file name generated is the prefix appended with the ISO 8601
date and time format and suffixed with .json extension. For example, `data-2020-09-02T14:30:00.json`
is the data for the time partition starting at 14:30:00 on 2020-09-02 and
extending through the end of duration (i.e., 30 minutes till 15:00:00).



# Interpolation

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

**Note:** The image was generated via the Web application. See the configuration
of Redis and the Web application for how to produce your own map-based interpolations.

# Running the application

The application is an interactive map that allows you to interact with the
AQI interpolation. You can select various time periods or run animations of
the AQI interpolations over a map.

The overall architecture is:

 * the data collection runs continuously storing the collected data into
   object storage (S3) in date/time partitions.

 * an ingestion process reads these partitions from object storage
   and store them into geospatial partitions in [Redis](https://redis.io) (i.e., via [GEOADD](https://redis.io/commands/geoadd)). These partitions are stored as separate keys in Redis to facilitate scale-out.

 * a Flask application provides an API for interacting with the data
   partitions, querying based on geospatial parameters, and running
   interpolations. In addition, it provides an interactive map-based
   interface to the data and interpolations.

## Quick start

Assuming you have your data collection running and likely storing data into
object storage (although, files will work), you can run everything locally
as a quick test.

 1. If you haven't already done so, setup a python environment and install the requirements:

    ```
    pip install -r requirements.txt
    ```

 1. Start redis:

    ```
    docker run -it --rm -p 6379:6379 redis
    ```

 1. Ingest some data.

    * if you have local files:

      ```
      python ingest.py --confirm --precision 0 --index 1 --type data file1.json file2.json ...
      ```
    * If you have data in object storage:

      ```
      python ingest.py --confirm --precision 0 --index 1 --type at --bucket-url https://storage.googleapis.com/yourbuckethere/data- 2020-09-10T00:00:00,2020-09-10T23:30:00
      ```

      For the above, the assumption is you've made your bucket of collected data
      publicly accessible. The date range specified will enumerate through the partitions which defaults to 30 minutes. You can change the partition size
      via the --partition parameter but this parameter must match the partitions
      you used for collection.

    The ingest program has a number of options for controlling what is ingested and
    how it finds the data

 1. Run the web application:

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

    Alternatively, all of the above settings can be set via environment variables
    or in the Flask configuration file (via the --config option).

    The keys are:

     * REDIS_HOST
     * REDIS_PORT
     * REDIS_PASSWORD
     * KEY_PREFIX
     * PARTITION

 1. Visit http://localhost:5000/

## Running on Kubernetes

The whole application can be run on Kubernetes:

 * *Data collection* - a long-running K8s Job,
 * *Redis* - a simple deployment or via the [Redis Enterprise Operator](https://github.com/RedisLabs/redis-enterprise-k8s-docs),
 * *Ingestion* - scheduled or ad-hoc K8s Jobs,
 * *Web Application* - via a Deployment.

For this setup, we'll using a single namespace:

```
kubectl create namespace redis-aqi
kubens redis-aqi
```

## Data Collection

A long-running Kubernetes job can be used to collect data. The job specification is located in [collection.yaml](collection.yaml).

### Setup the parameters

 1. Create the S3 credentials in a Secret:

   ```
   kubectl create secret generic s3 --from-literal=access-key-id=... "--from-literal=secret-access-key=..."
   ```

   For example, if you have stored your access key and secret in the standard environment variables:

   ```
   kubectl create secret generic s3 "--from-literal=access-key-id=${AWS_ACCESS_KEY_ID}" "--from-literal=secret-access-key=${AWS_SECRET_ACCESS_KEY}"
   ```

 1. Store the collection script in a ConfigMap:

   ```
   kubectl create configmap collect --from-file=collect.py=collect.py
   ```

 1. Setup the collection parameters

   ```
   kubectl create configmap parameters \
   --from-literal=box=38.41646632263371,-124.02669995117195,36.98663820370443,-120.12930004882817 \
   --from-literal=endpoint=https://storage.googleapis.com \
   --from-literal=bucket=yourbuckethere \
   --from-literal=interval=300 \
   --from-literal=partition=30
   ```

   Note: Amazon S3 endpoints can be [found here](https://docs.aws.amazon.com/general/latest/gr/s3.html) or
   you can omit the --endpoint parameter from the [collection.yaml](collection.yaml) job specification.

**Note:** if you need to update the python script or parameters, you can use the --dry-run parameter to kubectl. For example, the script can be updated with:

```
kubectl create configmap collect --from-file=collect.py=collect.py --dry-run -o yaml | kubectl apply -f -
```

### Start the collection job

The [collection.yaml](collection.yaml) file contains the job description. It can
be used without changes as the parameters are all in the ConfigMap and Secret
that was previously created.

Just the start the collection job via:

```
kubectl apply -f collection.yaml
```

### Monitoring collection

You can monitor the collection job by just examining the logs:

```
kubectl logs job/purpeair-collection
```

## Deploying Redis

You need a redis database to ingest and provide data to the application.

### Using a single-pod deployment

 1. Set your desired password in [redis.conf](redis.conf)
 1. Store the configuration in a ConfigMap:

    ```
    kubectl create configmap redis-config --from-file=redis.conf=redis.conf
    ```

 1. Deploy Redis:

    ```
    kubectl apply -f redis.yaml
    ```

 1. Deploy the Redis service:

    ```
    kubectl apply -f redis-service.yaml
    ```

### Using Redis Enterprise

If you don't have the operator installed, see the
[operator documentation](https://github.com/RedisLabs/redis-enterprise-k8s-docs)
for installation instructions.

If you don't have a cluster, you can create one by creating a custom resource
in the namespace (again, see the operator documentation). A small cluster
might be something like:

```
cat <<EOF > cluster.yaml
apiVersion: app.redislabs.com/v1
kind: RedisEnterpriseCluster
metadata:
  name: test
spec:
  nodes: 3
  redisEnterpriseNodeResources:
    limits:
      cpu: 3
      memory: 4Gi
    requests:
      cpu: 2
      memory: 4Gi
EOF
kubectl apply -f cluster.yaml
```

Once you have a cluster, you can just request a database of a certain size:

```
cat <<EOF > db.yaml
apiVersion: app.redislabs.com/v1alpha1
kind: RedisEnterpriseDatabase
metadata:
  name: aqi
spec:
  memorySize: 2GB
  redisEnterpriseCluster:
    name: test
EOF
kubectl apply -f db.yaml
```

The operator will create a service for the database called 'aqi' and the
connection parameters are contained in a secret called 'secret/redb-aqi'.
Specifically, the database password is stored in this secret.

The connection host is just the service DNS name (aqi.redis-aqi.svc)
and the port is the port listed on the service:

```
kubectl get service/aqi
```

### Configuring database access

This application use a secret called 'redis' for the host, password, and
port.

Create this secret with the parameters for your database:

```
kubectl create secret generic redis --from-literal=service=aqi.redis-aqi.svc --from-literal=port=... --from-literal=password=...
```

## Ingesting Data

Data ingestion can be run by the job [ingest.yaml](ingest.yaml). There is a
program called [job.py](job.py) that will adjust the parameters for the
particular date range you want to ingest along with other parameters.

First, store the ingest script in a ConfigMap:

```
kubectl create configmap ingest --from-file=ingest.py=ingest.py
```

The data will be pulled from the object storage where your data collection
is placing partitoins of data. For example, to ingest a single day:

```
python job.py --index 1 --type at 2020-09-14T00:00:00,2020-09-14T23:30:00 --name ingest-2020-09-14 | kubectl apply -f -
```

The configuration of the job is from:

 * The object storage parameters are taken from `configmap/parameters` that
   was created when you setup data collection.
 * The redis connection parameters are via `secret/redis`
 * The remaining parameters are set via the job.py configuration options

The job.py program has the same parameters as ingest.py. See their usage to
adjust the job creation.

## Running the Web application

The deployment [app.yaml](app.yaml) will deploy the Flask-based Web application
and relies on the image `alexmilowski/flask-aqi:2020-09-14-002`.

You can deploy the application via:

```
kubectl apply -f app.yaml
```

You can build your own version of this image via:

```
docker build . -t you/yourimage:version
```

and then just change the image reference in [app.yaml](app.yaml).

Once deployed, you can either create an ingress or forward the port to your
local machine:

```
kubectl port-forward `kubectl get pods --selector app=aqi -o jsonpath='{.items[0].metadata.name}'` 5000
```

Once forwarded, you can visit http://localhost:5000/
