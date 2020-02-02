import csv
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from measures.models import Place


class Command(BaseCommand):
    help = 'Populate places from Geoname country database'

    GEONAMES_DB_PATH = os.path.join(settings.DATA_DIR, 'geonames_PE.tsv')

    COLUMNS = {'name': 1, 'lat': 4, 'lon': 5}

    def handle(self, *args, **options):
        with open(self.GEONAMES_DB_PATH, 'r') as csvfile:
            reader = csv.reader(csvfile, delimiter='\t')
            for row in reader:
                row[4]
                print(row)

        # for poll_id in options['poll_ids']:
        #     try:
        #         poll = Poll.objects.get(pk=poll_id)
        #     except Poll.DoesNotExist:
        #         raise CommandError('Poll "%s" does not exist' % poll_id)

        #     poll.opened = False
        #     poll.save()

        #     self.stdout.write(self.style.SUCCESS(
        #         'Successfully closed poll "%s"' % poll_id))
