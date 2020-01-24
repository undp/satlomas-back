#!/bin/bash
set -e

export PGPASSWORD=$DB_PASSWORD 

echo "Create database $DB_NAME at $DB_HOST (user $DB_USER)"
psql -h "$DB_HOST" -U "$DB_USER" -c "CREATE DATABASE $DB_NAME";

echo "Run migrations"
pipenv run ./manage.py migrate

echo "Create super user"
pipenv run ./manage.py createsuperuser
