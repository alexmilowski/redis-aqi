FROM python:3.8

RUN mkdir /app
WORKDIR /app
ADD assets /app/assets
ADD templates /app/templates
COPY app.py /app
COPY ingest.py /app
COPY interpolate.py /app
COPY requirements.txt /app

RUN pip install -r requirements.txt
RUN pip install gunicorn

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "app:create_app()"]
