from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from jobs.utils import enqueue_job, run_job


class Command(BaseCommand):
    help = "Starts processing pipeline from MODIS VI, Sentinel-1 and Sentinel-2 sources"

    date_to = datetime.now().replace(day=1)
    date_from = date_to - relativedelta(months=1)
    tasks = ["modis_vi", "sentinel2"]

    def add_arguments(self, parser):
        parser.add_argument(
            "--date-from",
            type=lambda s: datetime.strptime(s, "%Y-%m-%d"),
            default=self.date_from,
        )
        parser.add_argument(
            "--date-to",
            type=lambda s: datetime.strptime(s, "%Y-%m-%d"),
            default=self.date_to,
        )
        parser.add_argument(
            "--sync",
            action="store_true",
            default=False,
            help="run job synchronously instead of enqueing job",
        )
        parser.add_argument(
            "--task",
            "-t",
            choices=self.tasks,
            default=None,
            help="task to process. If none, run all",
        )

    def handle(self, *args, **options):
        kwargs = dict(
            date_from=options["date_from"].strftime("%Y-%m-%d"),
            date_to=options["date_to"].strftime("%Y-%m-%d"),
            queue="processing",
        )

        if options["task"]:
            tasks = [options["task"]]
        else:
            tasks = self.tasks

        for task in tasks:
            job_method = f"eo_sensors.tasks.{task}.process_period"
            if options["sync"]:
                run_job(job_method, **kwargs)
            else:
                enqueue_job(job_method, **kwargs)
