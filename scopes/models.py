from django.contrib.gis.db import models
from django.contrib.gis.gdal import DataSource
from django.contrib.gis.geos import GEOSGeometry


class Scope(models.Model):
    CORREDORES = 'CE'
    ACR = 'AC'
    DISTRITOS = 'DI'
    ECOSISTEMAS = 'EF'
    ARQUEOLOGICOS = 'SA'
    SCOPE_TYPE = [
        (CORREDORES, 'Corredores Ecologicos'),
        (ACR, 'ACR'),
        (DISTRITOS, 'Distritos'),
        (ECOSISTEMAS, 'Ecosistemas fragiles'),
        (ARQUEOLOGICOS, 'Sitios arqueologicos'),
    ]

    scope_type = models.CharField(
        max_length=2,
        choices=SCOPE_TYPE,
    )
    geom = models.MultiPolygonField()
    name = models.CharField(max_length=64)

    def __str__(self):
        return "{} - {}".format(self.scope_type, self.name)
