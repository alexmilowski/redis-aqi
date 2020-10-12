---
title: Data Architecture
css: site.css
toc: false
---

# Sizing

This application uses the [geospatial features of OSS Redis](https://redis.io/commands#geo)
which have been available since version 3.2.0. The sensor data stored can
store several gigabytes of sensor readings per day. The amount of data can
increase or decrease depending on the interval and the geospatial region
of collection.

## Key Structure

Data is partitioned by a time period (e.g., 30 minutes) and stored into
a single geospatial sorted set via [GEOADD](https://redis.io/commands/geoadd).

Each partition is labeled:

```
prefix + datetime + duration
```

The datetime and duration are in [ISO 8601 format](https://en.wikipedia.org/wiki/ISO_8601).

For example, the default prefix is `AQI30-` and for a duration of 30 minutes:

```
AQI30-2020-10-12T11:30:00PT30M
```

is the data partition for the time period 11:30-12:00 on 2020-10-12.

## How Sensor Data is Stored

The score in a geospatial sorted set is a value computed from the location (a
geohash). As such, all the data for the sensor is encoded in the member that is
added to the set.

For every reading, we have two basic identifying facets:

 * *an identifier for the sensor*: This is typically a value assigned by the
   sensor network (i.e., an identifier assigned by PurpleAir).
 * *a time offset from the start time of partition*: The time of the sensor reading
   minus the start time of the partition is a simple offset value. This value
   can be rounded to minutes if precision is not required.

In addition, we have a set of reading values to store. In the case of air
quality sensors, these are the particulate matter readings for the current
time and a set of average values over different time periods
(e.g., last 10 minutes, last 30 minutes, etc.).

For this application the sensor readings are encoded as a comma separated
set of values where the first value is:

```
sensor + '@' + offset
```

and the remaining values are the retained sensor reading values rounded to
the desired precision. The ingestion process can choose which sensor
readings to ingest and the desired precision to limit the size of the stored
data or excessive number representation for transport.

For example, for a sensor with id 'B123' whose reading was taken at
2020-10-12T11:34:32 and the set of readings (145.5,150,148.9) is encoded
as the member:

```
B123@4,145.5,150,148.9
```

## Idempotency

The encoding of data as members ensures that the same sensor reading will
encode to the same set member. As such, ingesting the same data more than
once will still result in the set geospatial set. This make ingest idempotent.

As such, when ingest processes stop or fail, they can be restarted with
overlapping time periods. This ensures that all the data is ingested without
needing to query for the correct starting point. In turn, this makes the operation
of the data DevOps easier.

## Scaling

The amount of data stored in a single geospatial sorted set is related to the
partitioning used at ingest. By tuning the duration of the partition, the
amount of data per key can be tuned up or down (e.g., a longer duration means
more data).

The partitioning by datetime/duration also allows the keys to be split
amongst database shards.


## Database

A single database endpoint is all that is necessary to run the application. You
can run a local database for testing purposes via docker:

```
docker run -it --rm -p 6379:6379 redis
```

No modules are required.
