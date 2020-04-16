from datetime import datetime

from django.contrib.gis.db import models
from django.contrib.gis.geos.point import Point
from django.contrib.postgres.fields import JSONField
from django.utils.translation import gettext as _

from .managers import MeasurementManager, PredictionManager


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


class Measurement(models.Model):
    datetime = models.DateTimeField()
    station = models.ForeignKey(Station, on_delete=models.PROTECT)
    attributes = JSONField(blank=True)

    objects = MeasurementManager()

    class Meta:
        managed = False

    def __str__(self):
        return '{datetime} {station} :: {attributes}'.format(
            datetime=str(self.datetime),
            station=self.station,
            attributes=self.attributes)


class Prediction(models.Model):
    datetime = models.DateTimeField()
    station = models.ForeignKey(Station, on_delete=models.PROTECT)
    attributes = JSONField(blank=True)

    objects = PredictionManager()

    class Meta:
        managed = False

    def __str__(self):
        return '{datetime} {station} :: {attributes}'.format(
            datetime=str(self.datetime),
            station=self.station,
            attributes=self.attributes)
