import json

from django.contrib.postgres.fields.jsonb import KeyTextTransform
from django.db import connection, models
from django.db.models import Avg, Count, Func, Max, Min, Sum
from django.db.models.functions import Cast


class Year(Func):
    function = 'DATE_TRUNC'
    template = "%(function)s('year', %(expressions)s)"
    output_field = models.DateTimeField()


class Month(Func):
    function = 'DATE_TRUNC'
    template = "%(function)s('month', %(expressions)s)"
    output_field = models.DateTimeField()


class Week(Func):
    function = 'DATE_TRUNC'
    template = "%(function)s('week', %(expressions)s)"
    output_field = models.DateTimeField()


class Day(Func):
    function = 'DATE_TRUNC'
    template = "%(function)s('day', %(expressions)s)"
    output_field = models.DateTimeField()


class Hour(Func):
    function = 'DATE_TRUNC'
    template = "%(function)s('hour', %(expressions)s)"
    output_field = models.DateTimeField()


class MeasurementManager(models.Manager):
    grouping_intervals = dict(hour=Hour,
                              day=Day,
                              week=Week,
                              month=Month,
                              year=Year)
    aggregation_funcs = dict(avg=Avg, count=Count, max=Max, min=Min, sum=Sum)

    def create(self, datetime, station_id, attributes):
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO stations_measurement(datetime, station_id, attributes)
                VALUES ('{datetime}', '{station_id}', '{attributes}');
            """.format(datetime=str(datetime),
                       station_id=station_id,
                       attributes=json.dumps(attributes)))
            return self.model(datetime=datetime,
                              station_id=station_id,
                              attributes=attributes)

    def bulk_create(self, objs):
        with connection.cursor() as cursor:
            values = ', '.join([
                "('{datetime}', '{station_id}', '{attributes}')".format(
                    datetime=str(o.datetime),
                    station_id=o.station_id,
                    attributes=json.dumps(o.attributes)) for o in objs
            ])
            cursor.execute("""
                INSERT INTO stations_measurement(datetime, station_id, attributes)
                VALUES {values}
                ON CONFLICT DO NOTHING;
            """.format(values=values))

    def summary(self,
                grouping_interval='day',
                aggregation_func='avg',
                *,
                station,
                parameter,
                start,
                end):
        aggregation_func = self.aggregation_funcs[aggregation_func]
        grouping_interval = self.grouping_intervals[grouping_interval]

        qs = self.filter(station=station)
        qs = qs.filter(datetime__range=(start, end))
        qs = qs.annotate(t=grouping_interval('datetime')).values('t')
        qs = qs.annotate(v=aggregation_func(
            Cast(KeyTextTransform(parameter, 'attributes'),
                 models.FloatField())))
        qs = qs.order_by('t')
        return qs


class PredictionManager(models.Manager):
    def create(self, datetime, station_id, attributes):
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO stations_prediction(datetime, station_id, attributes)
                VALUES ('{datetime}', '{station_id}', '{attributes}');
            """.format(datetime=str(datetime),
                       station_id=station_id,
                       attributes=json.dumps(attributes)))
            return self.model(datetime=datetime,
                              station_id=station_id,
                              attributes=attributes)

    def bulk_create(self, objs):
        with connection.cursor() as cursor:
            values = ', '.join([
                "('{datetime}', '{station_id}', '{attributes}')".format(
                    datetime=str(o.datetime),
                    station_id=o.station_id,
                    attributes=json.dumps(o.attributes)) for o in objs
            ])
            cursor.execute("""
                INSERT INTO stations_prediction(datetime, station_id, attributes)
                VALUES {values}
                ON CONFLICT DO NOTHING;
            """.format(values=values))
