from django.conf import settings
from django_rq import job

from jobs.utils import run_command


@job
def start_proc_vm():
    cmd = settings.RUN_AFTER_ENQUEUE_PROC_JOB
    if cmd:
        run_command(settings.RUN_AFTER_ENQUEUE_PROC_JOB)
