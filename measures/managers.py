from django.db import models


class MeasureManager(models.Manager):
    def all(self):
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT m.datetime, m.station, m.temperature, m.humidity, m.wind_speed, m.wind_direction,
                m.pressure, m.precipitation, m.pm25
                FROM measures_measure m
                ORDER BY m.datetime DESC""")
            result_list = []
            for row in cursor.fetchall():
                m = self.model(datetime=row[0],
                               station=row[1],
                               temperature=row[2],
                               humidity=row[3],
                               wind_spped=row[4],
                               wind_direction=row[5],
                               pressure=row[6],
                               precipitation=row[7],
                               pm25=row[8])
                result_list.append(m)
        return result_list

    def create(self, datetime, station, temperature, humidity, wind_speed,
               wind_direction, pressure, precipitation, pm25):
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO measures_measure(datetime, station, temperature, humidity, wind_speed,
                wind_direction, pressure, precipitation, pm25)
                VALUES ('{datetime}', '{station}', {temperature}, {humidity}, {wind_speed},
                {wind_direction}, {pressure}, {precipitation}, {pm25});
            """.format(datetime=str(datetime),
                       station=station,
                       temperature=temperature,
                       humidity=humidity,
                       wind_speed=wind_speed,
                       wind_direction=wind_direction,
                       pressure=pressure,
                       precipitation=precipitation,
                       pm25=pm25))
            return self.model(datetime=datetime,
                              station=station,
                              temperature=temperature,
                              humidity=humidity,
                              wind_speed=wind_speed,
                              wind_direction=wind_direction,
                              pressure=pressure,
                              precipitation=precipitation,
                              pm25=pm25)

    def get(self, datetime, station):
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("""
            SELECT m.datetime, m.station, m.temperature, m.humidity, m.wind_speed, m.wind_direction,
                m.pressure, m.precipitation, m.pm25
            FROM measures_measure m
            where m.datetime = '{datetime}' and m.station = '{station}'
            """.format(datetime=str(datetime), station=station))
            result_list = []
            for row in cursor.fetchall():
                m = self.model(datetime=row[0],
                               station=row[1],
                               temperature=row[2],
                               humidity=row[3],
                               wind_spped=row[4],
                               wind_direction=row[5],
                               pressure=row[6],
                               precipitation=row[7],
                               pm25=row[8])
                result_list.append(m)
        if len(result_list) == 0:
            raise Exception("There is no results for that query")
        else:
            return result_list[0]
