#!/bin/bash
set -e

host="$1"
shift
cmd="$@"

echo "PostgreSQL is unavailable - sleeping and waiting"
until PGPASSWORD=$DB_PASSWORD psql -h "$host" -U "$DB_USER" -c '\q'; do
  sleep 1
done

>&2 echo "PostgreSQL is up - executing command"
exec $cmd
