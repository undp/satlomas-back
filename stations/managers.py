import json

from django.contrib.postgres.fields.jsonb import KeyTextTransform
from django.db import connection, models
from django.db.models import Avg, Count, Func, Max, Min, Sum, Window, F
from django.db.models.functions import Cast, Lag


def get_param_annotation(param, aggregation_func):
    return {
        param: aggregation_func(
            Cast(KeyTextTransform(param, "attributes"), models.FloatField())
        ),
    }


class Year(Func):
    function = "DATE_TRUNC"
    template = "%(function)s('year', %(expressions)s)"
    output_field = models.DateTimeField()


class Month(Func):
    function = "DATE_TRUNC"
    template = "%(function)s('month', %(expressions)s)"
    output_field = models.DateTimeField()


class Week(Func):
    function = "DATE_TRUNC"
    template = "%(function)s('week', %(expressions)s)"
    output_field = models.DateTimeField()


class Day(Func):
    function = "DATE_TRUNC"
    template = "%(function)s('day', %(expressions)s)"
    output_field = models.DateTimeField()


class Hour(Func):
    function = "DATE_TRUNC"
    template = "%(function)s('hour', %(expressions)s)"
    output_field = models.DateTimeField()


class Minute(Func):
    function = "DATE_TRUNC"
    template = "%(function)s('minute', %(expressions)s)"
    output_field = models.DateTimeField()


class MeasurementManager(models.Manager):
    grouping_intervals = dict(
        minute=Minute, hour=Hour, day=Day, week=Week, month=Month, year=Year
    )
    aggregation_funcs = dict(avg=Avg, count=Count, max=Max, min=Min, sum=Sum)

    def with_prev_attributes(self):
        prev_attributes = Window(
            expression=Lag("attributes"),
            partition_by=F("site"),
            order_by=F("datetime").asc(),
        )
        return self.annotate(prev_attributes=prev_attributes)

    def create(self, datetime, station_id, site_id, attributes):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO stations_measurement(datetime, station_id, site_id, attributes)
                VALUES ('{datetime}', '{station_id}', '{site_id}', '{attributes}');
            """.format(
                    datetime=str(datetime),
                    station_id=station_id,
                    site_id=site_id,
                    attributes=json.dumps(attributes),
                )
            )
            return self.model(
                datetime=datetime,
                station_id=station_id,
                site_id=site_id,
                attributes=attributes,
            )

    def bulk_create(self, objs):
        with connection.cursor() as cursor:
            values = ", ".join(
                [
                    "('{datetime}', '{station_id}', '{site_id}', '{attributes}')".format(
                        datetime=str(o.datetime),
                        station_id=o.station_id,
                        site_id=o.site_id,
                        attributes=json.dumps(o.attributes),
                    )
                    for o in objs
                ]
            )
            cursor.execute(
                """
                INSERT INTO stations_measurement(datetime, station_id, site_id, attributes)
                VALUES {values}
                ON CONFLICT DO NOTHING;
            """.format(
                    values=values
                )
            )

    def summary(
        self,
        grouping_interval="day",
        aggregation_func="avg",
        *,
        site,
        parameter,
        start,
        end
    ):
        aggregation_func = self.aggregation_funcs[aggregation_func]
        grouping_interval = self.grouping_intervals[grouping_interval]

        qs = self.filter(site=site)
        qs = qs.filter(datetime__range=(start, end))
        qs = qs.annotate(t=grouping_interval("datetime")).values("t")
        if len(parameter.split(",")) == 1:
            qs = qs.annotate(
                v=aggregation_func(
                    Cast(KeyTextTransform(parameter, "attributes"), models.FloatField())
                )
            )
        else:
            for param in parameter.split(","):
                qs = qs.annotate(**get_param_annotation(param, aggregation_func))
        qs = qs.order_by("t")
        return qs


class PredictionManager(models.Manager):
    def create(self, datetime, station_id, attributes):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO stations_prediction(datetime, station_id, attributes)
                VALUES ('{datetime}', '{station_id}', '{attributes}');
            """.format(
                    datetime=str(datetime),
                    station_id=station_id,
                    attributes=json.dumps(attributes),
                )
            )
            return self.model(
                datetime=datetime, station_id=station_id, attributes=attributes
            )

    def bulk_create(self, objs):
        with connection.cursor() as cursor:
            values = ", ".join(
                [
                    "('{datetime}', '{station_id}', '{attributes}')".format(
                        datetime=str(o.datetime),
                        station_id=o.station_id,
                        attributes=json.dumps(o.attributes),
                    )
                    for o in objs
                ]
            )
            cursor.execute(
                """
                INSERT INTO stations_prediction(datetime, station_id, attributes)
                VALUES {values}
                ON CONFLICT DO NOTHING;
            """.format(
                    values=values
                )
            )
