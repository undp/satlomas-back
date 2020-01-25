from datetime import datetime

from django.contrib.postgres.fields import JSONField
from django.contrib.gis.db import models

from .managers import MeasureManager


class Place(models.Model):
    parent_id = models.ForeignKey('self', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    geom = models.PolygonField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Device(models.Model):
    code = models.CharField(max_length=32)
    location = models.CharField(max_length=64)
    metadata = JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return '{code} - {location}'.format(code=self.code,
                                            location=self.location)


class Measure(models.Model):
    datetime = models.DateTimeField()
    temperature = models.FloatField(blank=True, null=True)
    humidity = models.FloatField(blank=True, null=True)
    device_id = models.TextField(blank=True, null=True)

    objects = MeasureManager()

    class Meta:
        managed = False

    def __str__(self):
        return '{datetime} {device_id} - Temp: {temp} Hum: {hum}'.format(
            datetime=str(self.datetime),
            device_id=self.device_id,
            temp=self.temperature,
            hum=self.humidity)
