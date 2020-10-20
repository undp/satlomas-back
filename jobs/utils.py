import logging
import subprocess

import django_rq


def run_command(cmd):
    logging.info(cmd)
    subprocess.run(cmd, shell=True, check=True)


def enqueue_job(method, queue=None, **kwargs):
    from jobs.models import Job
    job = Job.objects.create(name=method, kwargs=kwargs, queue=queue)
    job.start()
    return job