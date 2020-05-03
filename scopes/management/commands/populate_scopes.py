from django.core.management.base import BaseCommand
from django.conf import settings

from scopes.models import Scope
import os

SCOPE_TYPES_BY_NAME = {
    'acr': 'AC',
    'ecosistemas_fragiles': 'EF',
    'corredores_ecologicos': 'CE',
    'distritos': 'DI',
    'sitios_arqueologicos': 'SA',
}


class Command(BaseCommand):
    help = 'Populate Scope table with basic geojson of scopes'

    def add_arguments(self, parser):
        parser.add_argument('--scopes-path',
                            default=os.path.join(settings.BASE_DIR, 'data',
                                                 'scopes'))

    def handle(self, *args, **options):
        self.import_all_from_dir(options['scopes_path'])

    def import_all_from_dir(self, path):
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
            self.import_geojson(join(path, f))

    def import_geojson(self, path, scope_type=None):
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
            name, _ = os.path.splitext(os.path.basename(path))
            scope_type = SCOPE_TYPES_BY_NAME[name]

        ds = DataSource(path)
        layer = ds[0]

        epsg_id = layer.srs['AUTHORITY', 1]
        if epsg_id != '4326':
            raise RuntimeError(f"SRS is not epsg:4326 but epsg:{epsg_id}")

        for i, feature in enumerate(layer):
            if not feature['name']:
                raise RuntimeError(
                    f"Feature {i} from {path} has no 'name' field")

            geom = GEOSGeometry(feature.geom.wkt, srid=4326)
            scope, created = Scope.objects.get_or_create(
                scope_type=scope_type,
                name=str(feature['name']),
                defaults=dict(geom=geom))

            if created:
                self.log_success("{} - {} created.".format(
                    scope.scope_type, scope.name))
            else:
                self.log_success("{} - {} updated.".format(
                    scope.scope_type, scope.name))

    def log_success(self, msg):
        self.stdout.write(self.style.SUCCESS(msg))
