# Running on Serverless

The flask application (web application) can be run on AWS Lambda. This requires
building a packaging of the Flask application.

## Preparing the Build Script

The build script is a docker process that builds in the correct target
environment.

```
export DOCKERID=you
docker build . -t $DOCKERID/redis-aqi-lambda-build
```

## Building a distribution

The following will build a lambda.zip file for use on AWS Lambda

```
export BASE=$HOME/workspace/github
docker run --rm -v `pwd`:/build -v $BASE/redis-aqi/:/redis-aqi -v $BASE/flask-serverless/:/flask-serverless  $DOCKERID/redis-aqi-lambda-build:lates
```

You will need the supporting [flask-serverless](https://github.com/alexmilowski/flask-serverless) library cloned
locally and a sibling directory of this project.
