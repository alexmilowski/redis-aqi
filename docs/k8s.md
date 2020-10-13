---
title: Deploy on Kubernetes
css: site.css
toc: true
---

This is a complete guide to deploying the whole system on Kubernetes. The
data collection, ingest, Redis, and web application can be deployed within
a single namespace. Kubernetes allows for a scale-out deployment of ingest
and the Redis database. The web application can also be scaled independently from the
database and ingest workloads.

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
