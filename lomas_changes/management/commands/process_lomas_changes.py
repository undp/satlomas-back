from datetime import datetime, timedelta

import django_rq
from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand, CommandError
from jobs.utils import enqueue_job, run_job
from lomas_changes.tasks import sentinel1, sentinel2


class Command(BaseCommand):
    help = 'Starts processing pipeline from Sentinel-1 and Sentinel-2 sources'

    date_to = datetime.now().replace(day=1)
    date_from = date_to - relativedelta(months=1)

    def add_arguments(self, parser):
        parser.add_argument('--date-from',
                            type=lambda s: datetime.strptime(s, '%Y-%m-%d'),
                            default=self.date_from)
        parser.add_argument('--date-to',
                            type=lambda s: datetime.strptime(s, '%Y-%m-%d'),
                            default=self.date_to)

    def handle(self, *args, **options):
        kwargs = dict(date_from=options['date_from'].strftime('%Y-%m-%d'),
                      date_to=options['date_to'].strftime('%Y-%m-%d'),
                      queue='processing')

        # enqueue_job('lomas_changes.tasks.sentinel1.download_scene', **kwargs)
        # enqueue_job('lomas_changes.tasks.sentinel2.download_scene', **kwargs)
        run_job('lomas_changes.tasks.sentinel2.process_period', **kwargs)
