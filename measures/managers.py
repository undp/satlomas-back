import json

from django.contrib.postgres.fields.jsonb import KeyTextTransform
from django.db import connection, models
from django.db.models import Avg, Count, Func, Max, Min, Sum
from django.db.models.functions import Cast


class Year(Func):
    function = 'EXTRACT'
    template = '%(function)s(YEAR from %(expressions)s)'
    output_field = models.IntegerField()


class Month(Func):
    function = 'EXTRACT'
    template = '%(function)s(MONTH from %(expressions)s)'
    output_field = models.IntegerField()


class Week(Func):
    function = 'EXTRACT'
    template = '%(function)s(WEEK from %(expressions)s)'
    output_field = models.IntegerField()


class Day(Func):
    function = 'EXTRACT'
    template = '%(function)s(DAY from %(expressions)s)'
    output_field = models.IntegerField()


class MeasureManager(models.Manager):
    grouping_intervals = dict(day=Day, week=Week, month=Month, year=Year)
    aggregation_funcs = dict(avg=Avg, count=Count, max=Max, min=Min, sum=Sum)

    def create(self, datetime, station_id, attributes):
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO measures_measure(datetime, station_id, attributes)
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
                INSERT INTO measures_measure(datetime, station_id, attributes)
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
            Cast(KeyTextTransform(parameter, "attributes"),
                 models.FloatField())))
        qs = qs.order_by('-t')
        return qs
