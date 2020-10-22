FROM python:3.8

RUN pip install virtualenv
RUN apt-get update; apt-get install zip

CMD ["/build/dist.sh", "/build"]
