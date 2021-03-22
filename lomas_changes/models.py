from django.conf import settings
from django.contrib.gis.db import models
from django.conf import settings
from django.db.models import JSONField


def raster_path(instance, filename):
    return 'rasters/{path}/{filename}'.format(path=instance.path(),
                                              filename=filename)


class Raster(models.Model):
    slug = models.SlugField()
    date = models.DateField(null=True)
    file = models.FileField(upload_to=raster_path, blank=True, null=True)
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=255, blank=True)
    extra_fields = JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (('slug', 'date'), )

    def __str__(self):
        return f'{self.date} {self.name}'

    def tiles_url(self):
        return f'{settings.TILE_SERVER_URL}{self.path()}' + '{z}/{x}/{y}.png'

    def path(self):
        date_str = self.date.strftime('%Y%m%d')
        return f'{self.slug}/{date_str}/'


class CoverageRaster(models.Model):
    raster = models.ForeignKey(Raster, on_delete=models.CASCADE)
    cov_rast = models.RasterField(srid=32718)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class CoverageMeasurement(models.Model):
    date = models.DateField()
    scope = models.ForeignKey('scopes.Scope',
                              related_name="%(app_label)s_%(class)s_related",
                              on_delete=models.SET_NULL,
                              null=True)
    kind = models.CharField(max_length=2)
    area = models.FloatField()
    perc_area = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['date', 'scope', 'kind']

    def __str__(self):
        return '{date} :: {scope} :: {area}km2 ({perc_area}%)'.format(
            date=self.date,
            scope=self.scope and self.scope.name,
            area=self.area_km2(),
            perc_area=self.perc_area_100())

    def area_km2(self):
        return round(self.area / 1000000, 2)

    def perc_area_100(self):
        return round(self.perc_area * 100, 2)