import json

from django.db import connection, models


class MeasureManager(models.Manager):
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
                VALUES {values};
            """.format(values=values))
