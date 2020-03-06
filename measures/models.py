from datetime import datetime

from django.contrib.gis.db import models
from django.contrib.postgres.fields import JSONField
from django.utils.translation import gettext as _

from .managers import MeasureManager


class Place(models.Model):
    parent = models.ForeignKey('self',
                               on_delete=models.CASCADE,
                               null=True,
                               blank=True)
    name = models.CharField(max_length=255)
    geom = models.PolygonField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.parent_id:
            return '{parent} / {self}'.format(parent=self.parent,
                                              self=self.name)
        else:
            return self.name


class Station(models.Model):
    code = models.CharField(max_length=30, blank=True)
    name = models.CharField(max_length=255, blank=True)
    place = models.ForeignKey(Place,
                              on_delete=models.PROTECT,
                              blank=True,
                              null=True)
    lat = models.DecimalField(max_digits=10, decimal_places=6, null=True)
    lon = models.DecimalField(max_digits=10, decimal_places=6, null=True)
    geom = models.PointField()
    metadata = JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def place_name(self):
        return self.place.name if self.place else ''

    def save(self, *args, **kwargs):
        if not self.geom:
            self.geom = Point(self.lon, self.lat)
        super(Station, self).save(*args, **kwargs)

    def __str__(self):
        return '{name} ({code}) - {place}'.format(code=self.code,
                                                  name=self.name,
                                                  place=self.place)


class Measure(models.Model):
    datetime = models.DateTimeField()
    station = models.TextField(blank=True, null=True)

    temperature = models.FloatField(_("Environmental Temperature"),
                                    blank=True,
                                    null=True)
    humidity = models.FloatField(_("Relative Humidity"), blank=True, null=True)
    wind_speed = models.FloatField(_("Wind Speed"), blank=True, null=True)
    wind_direction = models.FloatField(_("Wind Direction"),
                                       blank=True,
                                       null=True)
    pressure = models.FloatField(_("Atmospheric Pressume"),
                                 blank=True,
                                 null=True)
    precipitation = models.FloatField(_("Precipitation"),
                                      blank=True,
                                      null=True)
    pm25 = models.FloatField(_("Particulate Matter (< 25um)"),
                             blank=True,
                             null=True)

    objects = MeasureManager()

    class Meta:
        managed = False

    def __str__(self):
        return '{datetime} :: {station} - Temp: {temp} Hum: {hum}'.format(
            datetime=str(self.datetime),
            station_id=self.station_id,
            temp=self.temperature,
            hum=self.humidity)
