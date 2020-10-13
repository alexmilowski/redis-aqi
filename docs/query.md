---
title: Querying Data
css: site.css
toc: false
---

In general, querying data is a simple process of using the [GEORADIUS](https://redis.io/commands/georadius)
command for the key that corresponds to a particular datatime partition. The
result is an encoded member value that can be decoded by splitting the
comma-separated value. The first value is the encoding the the sensor and
time offset into the partition. The remaining are the sensor readings.

## Querying quadrangles

A quadrangle is a rectangular-like area often specified by a northwest and
southeast pair of coordinates. As Redis has only radius-based queries, you
must compute the center and distance to one of the corners to cover the
quadrangle:

```
from haversine import haversine, Unit

nw, se = [(38,-124),(36,-120)]
lat_size = abs(nw[0] - se[0])
lon_size = abs(nw[1] - se[1])

# inscribe the quadrangle onto a circle with radius from center to
center = (nw[0] - lat_size/2, nw[1] + lon_size/2)
radius = haversine(center,nw,unit=Unit.KILOMETERS)
```


Using this location and radius may return results outside the quadrangle. The
results must be filter for members outside the boundaries:

```
import redis
client = redis.Redis()

result = client.georadius(
   partition_key,
   center[1],center[0],
   radius,unit='km',withcoord=True)

for key, pos in result:

   # Note: pos is lon, lat

   lat = pos[1]
   lon = pos[0]

   # check boundary
   if lat >= nw[0] or lat <= se[0] or lon <= nw[1] or lon >= se[1]:
      continue

   yield key, (lat,lon)

```

## Supporting functions

The [geo.py](https://github.com/alexmilowski/redis-aqi/blob/main/geo.py) library
provides helper generator functions that return matching encoded sensor
readings for various regions:

 * `query_circle(client, partition_key, center, radius, unit='km', bounds=None)` - query via a position and radius (like GEORADIUS)
 * `query_quadrangle(client, partition_key,nw,se)` - query via a quadrangle
 * `query_region(client,partition_key,nw,se,size=0.5,by_quadrangles=False)` - similar to `query_quadrangle` by divides the region into
   subqueries to reduce data transport size per query. By default, query_region uses sequence numbers to compute the covering.

For example:

```
import redis
client = redis.Redis()

for key, pos in geo.query_quadrangle(client,'AQI30-2020-09-27T00:00:00PT30M',nw,se):
   pass
```

## Quadrangles and Sequence Numbers

Regular quadrangles for a region of interest can be calculated by the
*quadrangles_for_bounds(size,nw,se)* function. It partitions the globe into a regular
covering of quadrangles and returns the quadrangles that covers the
input quadrangle:

```
for quadrangle in quadrangles_for_bounds(0.25,nw,se):
   print(quadrangle)
```

In [the report](/partitioning-geospatial-sensor-data.html), the concept of
sequence numbers is described. The supporting functions help with sequence
number related queries:

 * `sequence_number(size,p)` - the sequence for the quadrangle containing the point
 * `quadrangle_for_sequence_number(size,s)` - the quadrangle for the sequence number
 * `sequence_numbers_for_bounds(size,nw,se)` - the sequence numbers for the quadrangles
   that cover the input region
