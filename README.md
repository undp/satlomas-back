# SatLomas backend

This is the repository for SatLomas platform backend, which contains the REST
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

Youn can use `script/docker-run.sh` to run commands inside API container.
For example: `script/docker-run.sh pipenv run ./manage.py migrate` to run new
migrations.


### Without Docker

> **Note**: The following instructions are for Ubuntu 18.04.  You can check
> TimescaleDB instalation
> [guide](https://docs.timescale.com/latest/getting-started/installation) if
> you are using another OS.

Add PostgreSQL's third party repository to get the latest PostgreSQL packages
(if you are using Ubuntu older than 19.04):

```sh
# `lsb_release -c -s` should return the correct codename of your OS
echo "deb http://apt.postgresql.org/pub/repos/apt/ $(lsb_release -c -s)-pgdg main" | sudo tee /etc/apt/sources.list.d/pgdg.list
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt-get update
```

Add TimescaleDB's third party repository and install TimescaleDB, which will
download any dependencies it needs from the PostgreSQL repo:

```sh
# Add TimescaleDBs PPA
sudo add-apt-repository ppa:timescale/timescaledb-ppa
sudo apt-get update

# Now install appropriate package for PG version
sudo apt install timescaledb-postgresql-11
```

Tune database for TimescaleDB:

```sh
sudo timescaledb-tune
```

Install Python and other dependencies

```sh
sudo apt-get install \
  gdal-bin \
  gettext \
  libgdal-dev \
  libpq-dev \
  libproj-dev \
  python3 \
  python3-dev \
  python3-pip \
  redis-server
```

Install PostGIS 3 extension for this PostgreSQL.

```sh
sudo apt-get install postgresql-11-postgis-3
```

Restart PostgreSQL instance:

```sh
sudo service postgresql restart
```

Create a superuser role for your currently logged-in user:

```sh
sudo -u postgres createuser -s $USER
```

Create the database:

```sh
createdb geolomas
```

Set user password for the user you just created (`geolomas`). Please replace
`foobar` for a long and difficult to guess password:

```sh
psql geolomas -c "ALTER USER $USER WITH PASSWORD 'foobar'"
```

Add TimescaleDB and PostGIS extensions to the database

```sh
psql geolomas -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"
psql geolomas -c "CREATE EXTENSION IF NOT EXISTS postgis CASCADE"
```

* Copy `env.sample` and edit it to suit your needs. See the Configuration
  section above.

```sh
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

### Deployment

Copy the configuration files for systemd found at `tools/systemd`.

`gunicorn` start the Django service using gunicorn.

```sh
sudo cp tools/systemd/gunicorn.service /etc/systemd/system/
sudo systemctl start gunicorn.service
sudo systemctl enable gunicorn.service
```

`rqworker@` manages multiple workers for background jobs.

```sh
sudo cp tools/systemd/rqworker@.service /etc/systemd/system/
sudo systemctl start rqworker@.service
sudo systemctl enable rqworker@.service
```

If you make changes to those files after this, make sure then that systemd is
reloaded and restart services:

```sh
sudo systemctl daemon-reload
sudo systemctl restart gunicorn rqworker@*
```

Install nginx. Copy the configuration files found on `tools/nginx` and restart
nginx.

```
sudo apt install nginx
sudo cp tools/nginx/* /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/geolomas* /etc/nginx/sites-enabled/
sudo systemctl restart nginx
```

Install certbot and configure it for free SSL certificates and automatic
renewal:

```sh
sudo apt-get update
sudo apt-get install software-properties-common
sudo add-apt-repository universe
sudo add-apt-repository ppa:certbot/certbot
sudo apt-get update
```

```sh
sudo apt-get install certbot python-certbot-nginx
```

```sh
sudo certbot --nginx
```

## License

See [LICENSE.txt](LICENSE.txt)
