import json

from django.db import connection, models


class MeasureManager(models.Manager):
    def all(self):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT m.datetime, m.station_id, m.attributes
                FROM measures_measure m
                ORDER BY m.datetime DESC
            """)
            result_list = []
            for row in cursor.fetchall():
                m = self.model(datetime=row[0],
                               station_id=row[1],
                               attributes=row[2])
                result_list.append(m)
        return result_list

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

    def get(self, datetime, station_id):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT m.datetime, m.station_id, m.attributes
                FROM measures_measure m
                WHERE m.datetime = '{datetime}' and m.station = '{station}'
            """.format(datetime=str(datetime), station_id=station_id))
            result_list = []
            for row in cursor.fetchall():
                m = self.model(datetime=row[0],
                               station=row[1],
                               attributes=row[2])
                result_list.append(m)
        if len(result_list) == 0:
            raise Exception("There is no results for that query")
        else:
            return result_list[0]
