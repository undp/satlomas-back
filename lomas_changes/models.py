import uuid

from django.contrib.gis.db import models
from django.contrib.postgres.fields import JSONField


class Period(models.Model):
    date_from = models.DateField()
    date_to = models.DateField()

    def __str__(self):
        return '{} - {}'.format(self.date_from, self.date_to)


class Raster(models.Model):
    slug = models.SlugField()
    period = models.ForeignKey(Period, on_delete=models.PROTECT)
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=255, blank=True)
    area_geom = models.PolygonField()
    extra_fields = JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (('slug', 'period'), )

    def __str__(self):
        return f'{self.period} {self.name}'

    def tiles_url(self):
        return f'{settings.TILE_SERVER_URL}/{self.slug}' + '/{z}/{x}/{y}.png'

    def extent(self):
        """ Get area extent """
        return self.area_geom and self.area_geom.extent


class CoverageMeasurement(models.Model):
    date_from = models.DateField()
    date_to = models.DateField()
    scope = models.ForeignKey('scopes.Scope',
                              related_name="%(app_label)s_%(class)s_related",
                              on_delete=models.SET_NULL,
                              null=True)
    change_area = models.FloatField()
    perc_change_area = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['date_from', 'date_to', 'scope']

    def __str__(self):
        return '{dfrom}-{dto} :: {scope} :: {value} ({perc}%)'.format(
            dfrom=self.date_from,
            dto=self.date_to,
            scope=self.scope.name,
            value=self.change_area,
            perc=self.perc_change_area)
