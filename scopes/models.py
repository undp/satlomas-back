from django.contrib.gis.db import models
from django.contrib.gis.gdal import DataSource
from django.contrib.gis.geos import GEOSGeometry


class Scope(models.Model):
    CORREDORES = 'CO'
    TYPE_SCOPES = [
        (CORREDORES, 'Corredores'),
    ]
    type_scope = models.CharField(
        max_length=2,
        choices=TYPE_SCOPES,
    )
    period = models.DateField()
    poly = models.MultiPolygonField(srid=4326)
    name = models.CharField(max_length=64)

    #objects = models.GeoManager()
    @classmethod
    def save_from_geojson(cls, geojson_path, name, period, type_scope):
        ds = DataSource(geojson_path)
        feature = ds[0][0]
        wkt = feature.geom.wkt
        mp = GEOSGeometry(wkt)
        return cls.objects.create(
            type_scope=type_scope,
            period=period,
            name=name,
            poly=mp
        )