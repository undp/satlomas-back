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

    @classmethod
    def save_scope(cls, path, scope_type=None):
        """Save scopes from geojson

        Parameters
        ----------
        path : str
            The geojson path

        scope_type : str, optional
            Scope type, if None it will try to be completed by scope name
        """
        import os
        from django.contrib.gis.gdal import DataSource
        from django.contrib.gis.geos import GEOSGeometry

        if scope_type is None:
            scope_type = ""
            f = os.path.basename(path)
            if f.startswith("acr"):
                scope_type = "AC"
            elif f.startswith("ecosistemas"):
                scope_type = 'EF'
            elif f.startswith("corredores"):
                scope_type = 'CE'
            elif f.startswith("distritos"):
                scope_type = 'DS'
            elif f.startswith('sitios'):
                scope_type = 'SA'
            else:
                Exception("File doesn't match with any scope type")

        ds = DataSource(path)
        for x in range(0, len(ds[0])):
            feature = ds[0][x]
            mp = GEOSGeometry(feature.geom.wkt)
            return cls.objects.create(scope_type=scope_type,
                                      name=str(ds[0][x]['name']),
                                      geom=mp)

    @classmethod
    def initial_load(cls, path):
        """Initial load from geojson scopes

        Parameters
        ----------
        path : str
            The folder path that contains geojson scopes
        """
        import os
        from os.path import isfile, join
        scopes_files = [f for f in os.listdir(path) if isfile(join(path, f))]
        for f in scopes_files:
            cls.save_scope(join(path, f))
