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


class ChangesMask(models.Model):
    period = models.ForeignKey(Period, on_delete=models.PROTECT)
    mask = models.OneToOneField(Mask, on_delete=models.CASCADE)

    class Meta:
        unique_together = (('period', 'mask'), )

    def __str__(self):
        return f'ChangeMask: {self.mask}'


class VegetationMask(models.Model):
    period = models.DateField()
    vegetation = models.MultiPolygonField()
    clouds = models.MultiPolygonField()

    class Meta:
        app_label = 'vi_lomas_changes'

    def save_from_geojson(geojson_path, period):
        from django.contrib.gis.gdal import DataSource
        from django.contrib.gis.geos import GEOSGeometry
        import shapely.wkt
        from shapely.ops import unary_union

        ds = DataSource(geojson_path)
        vegetation_polys = []
        clouds_polys = []
        for x in range(0, len(ds[0]) - 1):
            geom = shapely.wkt.loads(ds[0][x].geom.wkt)
            if str(ds[0][x]['DN']) == '1':
                vegetation_polys.append(geom)
            elif str(ds[0][x]['DN']) == '2':
                clouds_polys.append(geom)
            else:
                pass
        vegetation_mp = unary_union(vegetation_polys)
        clouds_mp = unary_union(clouds_polys)

        return VegetationMask.objects.create(
            period=period,
            vegetation=GEOSGeometry(vegetation_mp.wkt),
            clouds=GEOSGeometry(clouds_mp.wkt))


class CoverageMeasurement(models.Model):
    date_from = models.DateField()
    date_to = models.DateField()
    scope = models.ForeignKey('scopes.Scope',
                              related_name="%(app_label)s_%(class)s_related",
                              on_delete=models.SET_NULL,
                              null=True)
    changes_mask = models.ForeignKey(ChangesMask,
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
