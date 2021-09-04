from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from jobs.utils import enqueue_job, run_job


class Command(BaseCommand):
    help = "Process and classify an already downloaded PeruSat-1 scene"

    def add_arguments(self, parser):
        parser.add_argument(
            "scene_dir",
        )
        parser.add_argument(
            "--sync",
            action="store_true",
            default=False,
            help="run job synchronously instead of enqueing job",
        )

    def handle(self, *args, **options):
        kwargs = dict(queue="processing", scene_dir=options["scene_dir"])

        job_method = f"eo_sensors.tasks.perusat1.pansharpen_scene"
        if options["sync"]:
            run_job(job_method, **kwargs)
        else:
            enqueue_job(job_method, **kwargs)
