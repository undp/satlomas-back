from datetime import datetime, timedelta

import django_rq
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Get modis rasters and create a vegetation layer'

    date_to = datetime.now()
    date_from = date_to - timedelta(days=60)

    def add_arguments(self, parser):
        parser.add_argument(
            '--date-from',
            type=lambda s: datetime.strptime(s, '%Y-%m-%d'),
            default=self.date_from,
            help="Init date to download the rasters. Format yyyy-mm-dd")
        parser.add_argument(
            '--date-to',
            type=lambda s: datetime.strptime(s, '%Y-%m-%d'),
            default=self.date_to,
            help="End date to download the rasters. Format yyyy-mm-dd")

    def handle(self, *args, **options):
        django_rq.enqueue('vi_lomas_changes.tasks.get_modis_peru',
                          options['date_from'], options['date_to'])
