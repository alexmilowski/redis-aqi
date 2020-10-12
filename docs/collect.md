---
title: Collecting Data
css: site.css
toc: false
---

The python program [collect.py](https://github.com/alexmilowski/redis-aqi/blob/main/collect.py)
provides a simple command line
interface to data collection that can poll at regular intervals and
collect the data from the API. This data is aggregated by the program and can
be stored in a variety of ways (e.g., in an S3-compatible object storage).

## Running data collection

This program can be run as:

```
# collect for the bay area every 5 minutes and partition by 30 minutes storing the result in an S3 bucket
python collect.py --bounding-box 38.41646632263371,-124.02669995117195,36.98663820370443,-120.12930004882817  --interval 300 --partition 30 --s3-bucket yourbuckethere
```

The program partitions data by a simple measuring the elapsed time between
collection intervals. You can tune the partitioning by the --interval and
--partition parameters. The data is either stored in a local directory,
specified by --dir, or in an S3-compatible object storage bucket, specified
by --s3-bucket

The S3 object storage can be configured via any of the [boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
configuration methods. The two simplest methods are to either specify the
access key and secret via the command-line paramaeters or in the
environemnt variables `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`.

In addition, a non-AWS S3-compatible object storage service can be used by providing
the endpoint URL. This is provided via the `--s3-endpoint` parameter.

Common options for the collection program are:

 * --bounding-box nwlat,nwlon,selat,selon

   The bounding box for collection; floating poing numbers representing the north west and south east corners of the quadrangle
 * --interval seconds

   The collection interval in seconds
 * --partition minutes

   The elapsed time in seconds at which to partition the data for storage
 * --prefix value

     The data file prefix
 * --dir dir

   A directory in which to store the data files
 * --s3-bucket name

   The S3 bucket name for storage
 * --s3-endpoint url

   A endpoint for the S3 protocol (e.g., https://storage.googleapis.com or [AWS endpoints](https://docs.aws.amazon.com/general/latest/gr/s3.html))
 * --s3-key aws_access_key_id

   The AWS access key

 * --s3-secret aws_secret_access_key

   The AWS secret access key

## Where data is stored

The collection program retrieves data from the API at the interval you
specify. It will aggregate the collected data until the partition time
limit has been reached and then store the tabular data as a JSON artifact. By
default, the data is sent to stdout in [JSON Text Sequences](https://tools.ietf.org/html/rfc7464).

In each case, the file name generated is the prefix appended with the ISO 8601
date and time format and suffixed with .json extension. For example, `data-2020-09-02T14:30:00.json`
is the data for the time partition starting at 14:30:00 on 2020-09-02 and
extending through the end of duration (i.e., 30 minutes till 15:00:00).

It should be noted that output file names are aligned to the partitions
you specify. For example, if you specify 30 minute periods of time, the
collection program will store to names with minutes of '00' and '30' only.
This may cause overwriting of collected data if the collection program is
restarted.
