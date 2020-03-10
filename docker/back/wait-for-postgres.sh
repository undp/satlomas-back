#!/bin/bash
set -e

host="$1"
shift
cmd="$@"

until PGPASSWORD=$DB_PASSWORD psql -h "$host" -U "$DB_USER" -c '\q'; do
  echo "PostgreSQL is unavailable - sleeping and waiting"
  sleep 1
done

>&2 echo "PostgreSQL is up - executing command"
exec $cmd
