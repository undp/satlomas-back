from datetime import datetime, timedelta

import django_rq
from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from vi_lomas_changes.models import Period
from vi_lomas_changes.tasks import process_all


class Command(BaseCommand):
    help = 'Get modis rasters and create a vegetation layer'

    date_to = datetime.now().replace(day=1)
    date_from = date_to - relativedelta(months=1)

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

    @transaction.atomic
    def handle(self, *args, **options):
        period, _ = Period.objects.get_or_create(
            date_from=options['date_from'], date_to=options['date_to'])
        process_all(period)
