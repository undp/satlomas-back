import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from measures.models import Place, Station
from django.contrib.gis.geos import Point


class Command(BaseCommand):
    help = 'Import fake station data, taken from SENAMHI'

    STATIONS_JSON_PATH = os.path.join(settings.DATA_DIR,
                                      'senamhi_stations.json')

    def handle(self, *args, **options):
        with open(self.STATIONS_JSON_PATH, 'r') as f:
            body = json.load(f)

        stations = body['stations']
        for station in stations:
            lat, lon = station['latlng']
            point = Point(lon, lat)
            place, _ = Place.objects.get_or_create(name=station['dep'])

            Station.objects.get_or_create(code=station['codigo'],
                                          defaults=dict(name=station['name'],
                                                        place=place,
                                                        lat=lat,
                                                        lon=lon,
                                                        geom=point))

        self.stdout.write(
            self.style.SUCCESS('Successfully generated {} stations'.format(
                len(stations))))
