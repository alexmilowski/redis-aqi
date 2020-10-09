---
title: Geospatial Air Quality Sensor Data in Redis
css: site.css
toc: false
---

This project provides a demonstration of the use of the geospatial
features of Redis to store and query air quality sensor readings. It provides
a complete process of collecting, ingesting, querying, and rendering
the raw sensor data to provide AQI (Air Quality Index) measurements
in a map-based web application.

The raw data is collected from air quality sensors (see [Data sources](#data-sources))
and is transformed into [AQI (Air Quality Index)](https://www.airnow.gov/aqi/aqi-basics/)
measurements and stored as in geospatial partitions.

The demonstration application is a simple Flask-based application
that creates a map-based interactive experience with the date/time and geospatial
partitions of the data which displays an interpolated (estimated) surface
of AQI measurements (see [Interpolation](#interpolation)).

## Data Sources

[PurpleAir sells](https://www.purpleair.com) air quality sensors that measure
particulate matter in the air and upload that data to a data repository. They
provide access to this [aggregated data via an API](https://docs.google.com/document/d/15ijz94dXJ-YAZLi9iZ_RaBwrZ4KtYeCy08goGBwnbCU/edit#heading=h.2tzq9j55gsj6).

At its simplest, the API returns a list of sensor readings for a given
bounding box defined by a pair of coordinate parameters defining the north west
and south east corners of the bounds. The resulting data contains the current
sensor data with rolling averages for the particulate matter readings.

PurpleAir provides documentation for how to turn the PM readings into an [AQI (Air Quality Index)](https://www.airnow.gov/aqi/aqi-basics/)
measure.

## What you can do next {.tiles}

### Collecting Data {.tile}

How data is collected from the air quality sensors and stored for
reuse. [Read](/collect.html)

### Data Architecture {.tile}

How to setup Redis / Redis Enterprise databases and how the data is stored
within keys. [Read](/data.html)

### Ingesting Data {.tile}

How to ingest raw sensor data into Redis. [Read](/ingest.html)

### Querying Data {.tile}

How to ingest raw sensor data into Redis. [Read](/query.html)

### Demo Application {.tile}

How to run the demo web application. [Read](/application.html)

### The Research {.tile}

For more information, read the full research report. [Read](/partitioning-geospatial-sensor-data.html)
