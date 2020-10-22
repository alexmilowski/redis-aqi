---
title: Ingesting Data
css: site.css
toc: false
---

## General Parameters

Data is ingest by reading a data source and using the [GEOADD](https://redis.io/commands/geoadd)
command. The individual commands are pipelined into batches of 1000 without
transactions.

When the data is read, the key for correct partition is computed for the
particular sensor reading. As such, the input data does not need to match the
output partitioning. That is, a single input data file can span multiple
partitions.

The [ingest.py](https://github.com/alexmilowski/redis-aqi/blob/main/ingest.py)
program has the following general parameters:

 * *--index* - any number of index parameters can be
   specified to pick specific readings from the source. Otherwise, all of the
   readings will be encoded
 * *--precision nnn* - the number of digits of precision can be
   specified for the encoded reading values. If not specified, the raw readings will be encoded.
 * *--partition mm* - the datetime data partition size in minutes. The default is 30.
 * *--host address* - the Redis host
 * *--port nnnn* - the Redis port
 * *--password passwd* - the Redis password
 * *--confirm* - output name the url or file being ingested (useful for logs or debugging)

The --type parameter controls how the source specification is interpreted and
from where the source data is read. The values allowed are:

 * *data* - (default) a set of local files or urls that contains the data
 * *urls* - list of files or urls whose content contains a list of urls of data resources
 * *now* - periods of time near now
 * *at* - periods of time from the range specified

The *now* and *at* source types only work with data stored in S3, accessible
by URI, and labeled in a regular scheme. The collection program ensures the
data store in S3 is labeled with a scheme that is compatible with this ingest
process.

If the data is stored in an S3-compatible service, you must specify the URL
of the bucket via the *--bucket-url* parameter. Direct access to the sources
via the S3 API is not currently supported. A simple way to enable access is
to make the bucket public or to setup a local proxy.

Note: The python requests library is used to access the data. Bearer access
tokens and other authentication methods are simple enhancements that can be
added to the `ingest_urls` function in [ingest.py](https://github.com/alexmilowski/redis-aqi/blob/main/ingest.py).

## Ingesting via local files:

Local files are ingested using the *--type data* parameter. The source files
are specified on the command:

  ```
  python ingest.py --confirm --precision 0 --index 1 --type data file1.json file2.json ...
  ```

## Ingesting via URLs:

Locations specified generically by URLs are ingested using the *--type urls* parameter. The source urls
are specified on the command:

  ```
  python ingest.py --confirm --precision 0 --index 1 --type data http://data.example.org/file1.json http://data.example.org/file2.json ...
  ```

## Ingesting by Date and Time

Once you have made your bucket accessible by a URL, there is a regular bucket
prefix. For example, a google object storage bucket might have the common
prefix:

```
https://storage.googleapis.com/yourbuckethere/data-
```

If the data was collected with [collect.py](https://github.com/alexmilowski/redis-aqi/blob/main/collect.py),
a partition for a certain datetime will just be the ISO 8601 datetime
with the '.json' suffix. Thus, the ingest program can just compute
certain datetime values to address collected data.

The *--ignore-not-found* parameter will ignore data partitions that are missing.

If you want the partitions nearest the current time, the *--type now*
parameter will compute the current and previous datetime partition as URLs.

If you specify *type at*, the list of sources are datetime ranges specified
by ISO 8601 formatted datetimes that are expanded by these rules:

 * a single date and time that represents a single source partition (e.g., `2020-09-10T11:30:00`)
 * a date time range specify by the start and end datetime separated by a comma (e.g., `2020-09-10T00:00:00,2020-09-10T23:30:00`). The default partition time of 30 minutes is assumed.
 * a date time range with the partition specified as a third comma-separated value (e.g., `2020-09-10T00:00:00,2020-09-10T23:30:00,30`)

The values are expanded into URLs and processed in the same way as if the urls where specified via the *--type urls* parameter.

For example, this invocation loads all the 30 minute partitions for the date 2020-09-10:

```
python ingest.py --confirm --precision 0 --index 1 --type at --bucket-url https://storage.googleapis.com/yourbuckethere/data- 2020-09-10T00:00:00,2020-09-10T23:30:00
```
