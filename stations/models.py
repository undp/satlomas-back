from auditlog.registry import auditlog
from django.contrib.gis.db import models
from django.db.models import JSONField
from django.contrib.postgres.fields import HStoreField
from django.utils.translation import gettext as _

from .managers import MeasurementManager, PredictionManager


class Station(models.Model):
    code = models.CharField(max_length=30)
    metadata = JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code


class Site(models.Model):
    name = models.CharField(max_length=255)
    geom = models.PointField()
    station = models.ForeignKey(
        Station, on_delete=models.SET_NULL, null=True, blank=True
    )
    attributes = HStoreField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Measurement(models.Model):
    datetime = models.DateTimeField()
    station = models.ForeignKey(Station, on_delete=models.PROTECT)
    site = models.ForeignKey(Site, on_delete=models.SET_NULL, blank=True, null=True)
    attributes = JSONField(blank=True)

    objects = MeasurementManager()

    class Meta:
        managed = False

    def __str__(self):
        return "{datetime} {station} :: {attributes}".format(
            datetime=str(self.datetime),
            station=self.station,
            attributes=self.attributes,
        )


class Prediction(models.Model):
    datetime = models.DateTimeField()
    station = models.ForeignKey(Station, on_delete=models.PROTECT)
    attributes = JSONField(blank=True)

    objects = PredictionManager()

    class Meta:
        managed = False

    def __str__(self):
        return "{datetime} {station} :: {attributes}".format(
            datetime=str(self.datetime),
            station=self.station,
            attributes=self.attributes,
        )


auditlog.register(Station)
