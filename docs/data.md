---
title: Data Architecture
css: site.css
toc: false
---

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

## Scaling

The amount of data stored in a single geospatial sorted set is related to the
partitioning used at ingest. By tuning the duration of the partition, the
amount of data per key can be tuned up or down (e.g., a longer duration means
more data).

The partitioning by datetime/duration also allows the keys to be split
amongst database shards.


## Run with Redis

A local application can run OSS Redis via docker:

```
docker run -it --rm -p 6379:6379 redis
```

No modules are required.
