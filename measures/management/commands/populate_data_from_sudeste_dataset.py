import json
import os
import pandas as pd

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from measures.models import Place, Station
from django.contrib.gis.geos import Point


class Command(BaseCommand):
    help = 'Import place, station and measurement data from sudeste dataset'

    CSV_PATH = os.path.join(settings.DATA_DIR,'sudeste.csv')

    def handle(self, *args, **options):

        dataset = pd.read_csv(
            self.CSV_PATH, 
            header=0, index_col=0,nrows=None)


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
