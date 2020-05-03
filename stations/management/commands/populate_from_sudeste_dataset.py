import json
import os
from datetime import datetime

import pandas as pd
from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError

from stations.models import Measurement, Place, Station


def chunker(seq, size):
    return (seq[pos:pos + size] for pos in range(0, len(seq), size))


# Suggestion: Run command like this
# python manage.py populate_data_from_sudeste_dataset >> populate_data.log 2>&1
class Command(BaseCommand):
    help = 'Import place, station and measurement data from sudeste dataset'

    CSV_PATH = os.path.join(settings.DATA_DIR, 'sudeste_sample.csv')
    CHUNK_SIZE = 10000

    def handle(self, *args, **options):
        dataset = pd.read_csv(self.CSV_PATH, header=0, index_col=0, nrows=None)
        self.log_success('Shape of the original csv {}'.format(dataset.shape))

        # Drop data to make it managable
        dataset = dataset.loc[dataset.yr > 2010]

        dataset.fillna(0, inplace=True)

        self.log_success('Shape of the filtered csv {}'.format(dataset.shape))

        # Get all the different cities in the dataset
        unique_cities = dataset.city.unique()

        for city in unique_cities:
            self.log_success('Creating place for city {}'.format(city))
            place, created = Place.objects.get_or_create(name=city)
            if created:
                self.log_success('Place for {} created'.format(city))
            else:
                self.log_success('Place for {} already exists'.format(city))

            # Create the stations of the city
            # work with a the slice of the dataset for that city dataset.loc[dataset.city == city]

            unique_stations = dataset.loc[dataset.city == city].inme.unique()
            for station_code in unique_stations:
                # Work with slice for city and station
                #dataset.loc[dataset.city == city].loc[dataset.loc[dataset.city == city].inme == station_code]

                first = dataset.loc[dataset.city == city].loc[dataset.loc[
                    dataset.city == city].inme == station_code].iloc[0]

                # self.log_success('Creating station {}'.format(station_code))
                station, created = Station.objects.get_or_create(
                    code=station_code,
                    name=first.wsnm,
                    lat=float(first.lat),
                    lon=float(first.lon),
                    place=place)
                if created:
                    self.log_success('Station {} created: {}'.format(
                        station_code, station))
                else:
                    self.log_success(
                        'Station {} already exists'.format(station))

                # Get all measurements for station, probably simulating or
                # imputing values between hours.
                station_dataset = dataset.loc[dataset.inme == station_code]
                for chunk in chunker(station_dataset, self.CHUNK_SIZE):
                    objs = [
                        m
                        for i in range(len(chunk))
                        for m in self.new_measurements(station, chunk.iloc[i])
                    ]
                    Measurement.objects.bulk_create(objs)
                    self.log_success("{} measurements loaded.".format(
                        len(chunk)))

    def new_measurements(self, station, measurement):
        direction = 1
        res = []
        for minute in [0, 15, 30, 45]:
            year, month, day, hour = measurement.yr, measurement.mo, measurement.da, measurement.hr
            ts = datetime(year, month, day, hour, minute, 0, 0)

            delta_min = direction * 0.02 * minute
            direction = direction * -1

            attributes = dict(temperature=measurement.temp + delta_min,
                              humidity=measurement.hmdy + delta_min,
                              wind_speed=measurement.wdsp + delta_min,
                              wind_direction=measurement.wdct + delta_min,
                              pressure=measurement.stp + delta_min,
                              precipitation=measurement.prcp + delta_min,
                              pm25=measurement.prcp * 2 + delta_min)
            res.append(Measurement(datetime=ts,
                                   station=station,
                                   attributes=attributes))
        return res

    def log_success(self, msg):
        self.stdout.write(self.style.SUCCESS(msg))

    def log_error(self, msg):
        self.stderr.write(self.style.ERROR(msg))
