#!/bin/bash
docker-compose down
docker-compose run api wait-for-postgres.sh db docker/back/init.sh
echo "Reset done. Now run 'docker-compose up' to start API and workers."
