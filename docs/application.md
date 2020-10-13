---
title: Demo Application
css: site.css
toc: false
---

The demo application is a flask-based application that you can run directly.
All it needs is the connection parameters for the Redis database.

1. Start the web application:

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
