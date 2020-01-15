from django.core.management.base import BaseCommand, CommandError
import django_rq 
from datetime import datetime, timedelta

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
        queue = django_rq.get_queue('default', default_timeout=36000)
        queue.enqueue("files.tasks.sentinel1.download_scenes",options['date_from'], options['date_to'])
        queue.enqueue("files.tasks.sentinel2.download_sentinel2",options['date_from'], options['date_to'])
       

        
