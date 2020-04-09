from datetime import datetime, timedelta

import django_rq
from django.core.management.base import BaseCommand, CommandError

from lomas_changes.models import Period


class Command(BaseCommand):
    help = 'comando para bajar imagenes de sentinel 1 y sentinel 2'

    date_to = datetime.now()
    date_from = date_to - timedelta(days=60)

    def add_arguments(self, parser):
        parser.add_argument('--date-from',
                            type=lambda s: datetime.strptime(s, '%Y-%m-%d'),
                            default=self.date_from)
        parser.add_argument('--date-to',
                            type=lambda s: datetime.strptime(s, '%Y-%m-%d'),
                            default=self.date_to)

    def handle(self, *args, **options):
        period = Period.objects.create(init_date=options['date_from'],
                                       end_date=options['date_to'])
        queue = django_rq.get_queue('default', default_timeout=36000)
        queue.enqueue("lomas_changes.tasks.sentinel1.download_scenes", period)
        queue.enqueue("lomas_changes.tasks.sentinel2.download_sentinel2",
                      period)
