from django.conf import settings
from django.contrib.gis.db import models
from django.conf import settings
from django.contrib.postgres.fields import JSONField


def raster_path(instance, filename):
    return 'rasters/{path}/{filename}'.format(path=instance.path(),
                                              filename=filename)


class Period(models.Model):
    date_from = models.DateField()
    date_to = models.DateField()

    class Meta:
        unique_together = (('date_from', 'date_to'), )

    def __str__(self):
        return '{} - {}'.format(self.date_from, self.date_to)


class Raster(models.Model):
    slug = models.SlugField()
    period = models.ForeignKey(Period, on_delete=models.PROTECT)
    file = models.FileField(upload_to=raster_path, blank=True, null=True)
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=255, blank=True)
    extent_geom = models.PolygonField(blank=True, null=True)
    extra_fields = JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (('slug', 'period'), )

    def __str__(self):
        return f'{self.period} {self.name}'

    def tiles_url(self):
        return f'{settings.TILE_SERVER_URL}{self.path()}' + '{z}/{x}/{y}.png'

    def path(self):
        date_from = self.period.date_from.strftime('%Y%m%d')
        date_to = self.period.date_to.strftime('%Y%m%d')
        return f'{self.slug}/{date_from}-{date_to}/'

    def extent(self):
        """ Get area extent """
        return self.area_geom and self.area_geom.extent


class Mask(models.Model):
    period = models.ForeignKey(Period, on_delete=models.PROTECT)
    mask_type = models.CharField(max_length=32, blank=True, null=True)
    geom = models.MultiPolygonField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (('period', 'mask_type'), )

    def __str__(self):
        return f'{self.period} {self.mask_type}'


class Object(models.Model):
    period = models.ForeignKey(Period, on_delete=models.PROTECT)
    object_type = models.CharField(max_length=8, blank=True, null=True)
    geom = models.PolygonField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.period} {self.object_type}'


class CoverageMeasurement(models.Model):
    date_from = models.DateField()
    date_to = models.DateField()
    scope = models.ForeignKey('scopes.Scope',
                              related_name="%(app_label)s_%(class)s_related",
                              on_delete=models.SET_NULL,
                              null=True)
    area = models.FloatField()
    perc_area = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['date_from', 'date_to', 'scope']

    def __str__(self):
        return '{dfrom}-{dto} :: {scope} :: {area}km2 ({perc_area}%)'.format(
            dfrom=self.date_from,
            dto=self.date_to,
            scope=self.scope and self.scope.name,
            area=self.area_km2(),
            perc_area=self.perc_area_100())

    def area_km2(self):
        return round(self.area / 1000000, 2)

    def perc_area_100(self):
        return round(self.perc_area * 100, 2)