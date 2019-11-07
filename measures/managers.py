from django.db import models

class MeasureManager(models.Manager):
    def all(self):
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT m.datetime, m.temperature, m.humidity, m.device_id
                FROM measures_measure m
                ORDER BY m.datetime DESC""")
            result_list = []
            for row in cursor.fetchall():
                m = self.model(datetime=row[0], temperature=row[1], humidity=row[2], device_id=row[3])
                result_list.append(m)
        return result_list

    def create(self, datetime, temperature, humidity, device_id):
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO measures_measure(datetime, temperature, humidity, device_id)
                VALUES ('{datetime}', {temperature}, {humidity}, '{device_id}');
            """.format(
                datetime=str(datetime),
                temperature=temperature,
                humidity=humidity,
                device_id=device_id
            ))
            return self.model(
                datetime=datetime, 
                temperature=temperature, 
                humidity=humidity, 
                device_id=device_id
            )