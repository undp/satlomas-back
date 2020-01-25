# GeoLomas backend

This is the repository for GeoLomas platform backend, which contains the REST
API and background jobs.


## Requirements

* Python 3
* PostgreSQL 9.4+ with PostGIS 2 and Timescale extensions
* GDAL, Proj, etc.


## Configuration

Copy `env.sample` as `.env`, and edit it to suit your needs. The following
variables are mandatory:

- `SECRET_KEY`: This is used to provide cryptographic signing, and should be
  set to a unique, unpredictable string value.
- `SCIHUB_USER`: SciHub username. Needed for downloading Sentinel-1/2 datasets.
- `SCIHUB_PASS`: SciHub password. Needed for downloading Sentinel-1/2 datasets.
- `MODIS_USER`: USGS username. Needed for downloading MODIS datasets.
- `MODIS_PASS`: USGS password. Needed for downloading MODIS datasets.


## Development

### With Docker

There is a set of Docker images and docker-compose configuration file that
manages all services:

* `api` Django app instance for API and Admin
* `worker`: RQ worker instance
* `db`: PostgreSQL instance with TimescaleDB and PostGIS extensions

You only need to have Docker and Docker Compose installed.

First step is to run `script/docker-reset.sh` to create database, run
migrations and create super user.

Afterwards, run `docker-compose up`. If you want to run everything in the
background, use `docker-compose start`, and afterwards `docker-compose stop` to
stop everything.

If you need to reset again, just run `script/docker-reset.sh`.  To stop
everything and delete all volumes and networks run `docker-compose down`.

Youn can use `script/docker-run.sh` to run commands inside Pipenv virtual env.
For example: `script/docker-run.sh ./manage.py migrate` to run new migrations.


### Without Docker

* Install dependencies

```
sudo apt-get install python3 python3-dev python3-pip \
  libgdal-dev libproj-dev postgresql postgis \
  gettext
```

* Install TimescaleDB

You can use TimescaleDB instalation
[guide](https://docs.timescale.com/latest/getting-started/installation).

* Create a role and database (e.g. `geolomas`)

```
sudo -u postgres createuser -s --interactive
sudo -u postgres createdb geolomas
```

* Set user password for Django

```
$ psql geolomas
# ALTER USER geolomas WITH PASSWORD 'foobar';
```

* Extends the database

```
# CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
```

* Copy `env.sample` and edit it to suit your needs. You will have to set
  `DB_USER`, `DB_PASS` and `DB_NAME`.

```
cp env.sample .env
```

* Install Python dependencies using Pipenv. Install it first if you don't have it:

```
pip install --user -U pipenv
pipenv install
pipenv install django-anymail[mailgun] django-rest-auth[with_social] django-storages[google]
```

Then inside a pipenv shell (use `pipenv shell`) you should first do the following:

* Run migrations: `./manage.py migrate`
* Create superuser: `./manage.py createsuperuser`

Now you can:

* Run server: `./manage.py runserver`
* Run tests: `./manage.py test`

When deploying for the first time:

* Set `DEBUG=0` and `ALLOWED_HOSTS` list with domains/subdomains and IPs
* Also, set a long unique `SECRET_KEY`
* Collect statics with `./manage.py collectstatic`

### Honcho

You can use [Honcho](https://honcho.readthedocs.io) to fire up everything (web
server, workers and Flower) on your dev machine. Simple run `honcho start`.
You can also start specific processes: `honcho start web`, `honcho start
worker`, etc.

See [Procfile](Procfile).

### Translations

When adding new translated strings:

* Run `django-admin makemessages`
* Update .po files
* Run `django-admin compilemessages`
