FROM python:3.6

ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y --no-install-recommends \
    binutils \
    gdal-bin \
    gettext \
    libpq-dev \
    libproj-dev \
    postgresql-client \
    python3-dev \
  && rm -rf /var/lib/apt/lists/*

RUN pip install -U pipenv==2018.11.26

RUN mkdir /app
WORKDIR /app

COPY Pipfile Pipfile.lock /app/
RUN pipenv install \
  && pipenv install django-anymail[mailgun] django-rest-auth[with_social]

COPY docker/wait-for-postgres.sh \
  /usr/local/bin/

EXPOSE 8000
