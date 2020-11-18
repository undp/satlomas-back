#!/bin/bash

pipenv run ./manage.py check_jobs --queue processing

if [ $? -ne 0 ]; then
  echo "There are no jobs to process. Shutting down now..."
  sudo shutdown -h now
fi
