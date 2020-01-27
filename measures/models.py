from datetime import datetime

from django.contrib.postgres.fields import JSONField
from django.contrib.gis.db import models

from .managers import MeasureManager


class Place(models.Model):
    parent_id = models.ForeignKey('self',
                                  on_delete=models.CASCADE,
                                  null=True,
                                  blank=True)
    name = models.CharField(max_length=255)
    geom = models.PolygonField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Station(models.Model):
    name = models.CharField(max_length=255, blank=True)
    place_id = models.ForeignKey('Place',
                                 on_delete=models.PROTECT,
                                 blank=True,
                                 null=True)
    lat = models.DecimalField(max_digits=10, decimal_places=6, null=True)
    lon = models.DecimalField(max_digits=10, decimal_places=6, null=True)
    geom = models.PointField()
    metadata = JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.geom:
            self.geom = Point(self.lon, self.lat)
        super(Station, self).save(*args, **kwargs)

    def __str__(self):
        return '[{code}] {name} - {place_name}'.format(
            code=self.code, name=self.name, place_name=self.place.name)


class Measure(models.Model):
    datetime = models.DateTimeField()
    station_id = models.TextField(blank=True, null=True)

    temperature = models.FloatField(blank=True, null=True)
    humidity = models.FloatField(blank=True, null=True)

    objects = MeasureManager()

    class Meta:
        managed = False

    def __str__(self):
        return '{datetime} {station_id} - Temp: {temp} Hum: {hum}'.format(
            datetime=str(self.datetime),
            station_id=self.station_id,
            temp=self.temperature,
            hum=self.humidity)
