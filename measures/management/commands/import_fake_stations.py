import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from measures.models import Station


class Command(BaseCommand):
    help = 'Import fake station data, taken from SENAMHI'

    STATIONS_JSON_PATH = os.path.join(settings.DATA_DIR,
                                      'senamhi_stations.json')

    def handle(self, *args, **options):
        with open(self.STATIONS_JSON_PATH, 'r') as f:
            body = json.load(f)
            print(body)

        # for poll_id in options['poll_ids']:
        #     try:
        #         poll = Poll.objects.get(pk=poll_id)
        #     except Poll.DoesNotExist:
        #         raise CommandError('Poll "%s" does not exist' % poll_id)

        #     poll.opened = False
        #     poll.save()

        #     self.stdout.write(self.style.SUCCESS(
        #         'Successfully closed poll "%s"' % poll_id))
