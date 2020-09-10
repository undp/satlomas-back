#!/bin/bash
set -e

host="$1"
shift
cmd="$@"

until psql -h "$host" -c '\q'; do
  echo "PostgreSQL is unavailable - sleeping and waiting"
  sleep 1
done

>&2 echo "PostgreSQL is up - executing command"
exec $cmd
