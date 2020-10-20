import logging
import subprocess

import django_rq
from django.conf import settings


def run_command(cmd):
    logging.info(cmd)
    subprocess.run(cmd, shell=True, check=True)


def enqueue_processing_job(method, *args, **kwargs):
    queue = django_rq.get_queue('process')
    queue.enqueue(method, *args, **kwargs)

    cmd = settings.RUN_AFTER_ENQUEUE_PROC_JOB
    if cmd:
        run_command(cmd)
