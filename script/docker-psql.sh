#!/bin/bash
docker-compose run api wait-for-postgres.sh db docker/back/psql.sh
