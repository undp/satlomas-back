#!/bin/bash
set -e

echo "Create database $PGDATABASE at $PGHOST (user $PGUSER)"
psql -c "CREATE DATABASE $PGDATABASE";

echo "Run migrations"
pipenv run ./manage.py migrate

echo "Create super user"
pipenv run ./manage.py createsuperuser
