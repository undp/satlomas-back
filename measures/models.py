from django.db import models
from datetime import datetime
from .managers import MeasureManager


class Device(models.Model):
    code = models.CharField(max_length=32)
    location = models.CharField(max_length=64)

    def __str__(self):
        return '{code} - {location}'.format(code=self.code,
                                            location=self.location)     
"""
Run in SQL
CREATE TABLE measures_measure (
    datetime TIMESTAMP not null, 
    temperature float, 
    humidity float, 
    device_id text not null, 
    PRIMARY KEY(datetime, device_id)
);
SELECT create_hypertable('measures_measure','datetime');
"""

class Measure(models.Model):
    datetime = models.DateTimeField()
    temperature = models.FloatField(blank=True, null=True)
    humidity = models.FloatField(blank=True, null=True)
    device_id = models.TextField(blank=True, null=True)

    objects = MeasureManager()

    class Meta:
        managed = False
        db_table = 'measures_measure'

    
    def __str__(self):
        return '{datetime} {device_id} - Temp: {temp} Hum: {hum}'.format(
            datetime=str(self.datetime),
            device_id=self.device_id,
            temp=self.temperature,
            hum=self.humidity
        )
