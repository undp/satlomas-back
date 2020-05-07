from datetime import datetime

from django.core.management.base import BaseCommand

from lomas_changes.models import Period
from lomas_changes.tasks.perusat1 import load_data


class Command(BaseCommand):
    help = 'Loads an already processed PeruSat-1 image and object detection results'

    def add_arguments(self, parser):
        parser.add_argument('--product-id', required=True)
        parser.add_argument('--date',
                            type=lambda s: datetime.strptime(s, '%Y-%m-%d'),
                            required=True)

    def handle(self, *args, **options):
        date = options['date'].date()
        product_id = options['product_id']

        period, _ = Period.objects.get_or_create(date_from=date, date_to=date)
        load_data(period, product_id)
