import logging
import subprocess
import sys

import django_rq

# Configure logger
logger = logging.getLogger(__name__)
out_handler = logging.StreamHandler(sys.stdout)
out_handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
out_handler.setLevel(logging.INFO)
logger.addHandler(out_handler)
logger.setLevel(logging.INFO)


def job(func_or_queue, connection=None, *args, **kwargs):
    """Job decorator"""
    def wrapper(func):
        def monitored_func(job_pk):
            from jobs.models import Job
            job = Job.objects.get(pk=job_pk)

            try:
                func(job)
            except Exception as err:
                # TODO: Add traceback
                job.mark_as_failed(reason=err)
            else:
                job.mark_as_finished()

        rq_job_wrapper = django_rq.job(func_or_queue,
                                       connection=connection,
                                       *args,
                                       **kwargs)
        return rq_job_wrapper(monitored_func)

    return wrapper


def run_command(cmd):
    logging.info(cmd)
    subprocess.run(cmd, shell=True, check=True)


def enqueue_job(method, queue=None, **kwargs):
    from jobs.models import Job

    logger.info("Create next job %s with kwargs: %s, on queue '%s'", method,
                kwargs, queue)
    job = Job.objects.create(name=method, kwargs=kwargs, queue=queue)
    job.start()
    return job
