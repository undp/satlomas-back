import logging
import os
import sys

import geopandas as gpd
import numpy as np
import rasterio
import shapely.wkt
from django.conf import settings
from django.contrib.gis.gdal import DataSource
from django.contrib.gis.geos import GEOSGeometry
from django.core.files import File
from django.db import DatabaseError, connection, transaction
from shapely.ops import unary_union

from lomas_changes.models import CoverageMeasurement, Mask, Raster
from scopes.models import Scope

# Configure logger
logger = logging.getLogger(__name__)
out_handler = logging.StreamHandler(sys.stdout)
out_handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
out_handler.setLevel(logging.INFO)
logger.addHandler(out_handler)
logger.setLevel(logging.INFO)

DATA_DIR = os.path.join(settings.BASE_DIR, 'data', 'lomas_changes')
MASK_DIR = os.path.join(DATA_DIR, 'mask')
RGB_DIR = os.path.join(DATA_DIR, 'rgb')


def load_data(period):
    #post_process(period)
    create_mask_rgb_raster(period)
    create_masks(period)
    generate_measurements(period)


def create_mask_rgb_raster(period):
    period_s = '{dfrom}_{dto}'.format(dfrom=period.date_from.strftime("%Y%m"),
                                      dto=period.date_to.strftime("%Y%m"))

    logger.info("Build RGB loss mask raster")
    src_path = os.path.join(MASK_DIR, period_s, 'cover.tif')
    dst_path = os.path.join(RGB_DIR, period_s, 'loss.tif')
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    write_loss_mask_rgb_raster(src_path=src_path, dst_path=dst_path)

    raster, _ = Raster.objects.update_or_create(
        period=period, slug="loss", defaults=dict(name="Loss mask"))
    with open(dst_path, 'rb') as f:
        if raster.file:
            raster.file.delete()
        raster.file.save(f'loss.tif', File(f))


def write_loss_mask_rgb_raster(src_path, dst_path):
    with rasterio.open(src_path) as src:
        img = src.read(1)
        profile = src.profile.copy()

    colormap = ['ff0000']
    new_img = np.zeros((img.shape[0], img.shape[1], 3), dtype=np.uint8)
    for i in range(len(colormap)):
        new_img[img == i + 1] = hex_to_dec_string(colormap[i])

    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    profile.update(count=3, dtype=np.uint8, nodata=0)
    with rasterio.open(dst_path, 'w', **profile) as dst:
        for i in range(new_img.shape[2]):
            dst.write(new_img[:, :, i], i + 1)


def create_masks(period):
    period_s = '{dfrom}_{dto}'.format(dfrom=period.date_from.strftime("%Y%m"),
                                      dto=period.date_to.strftime("%Y%m"))

    logging.info("Reproject to epsg:4326")
    src_path = os.path.join(MASK_DIR, period_s, 'cover.geojson')
    dst_path = os.path.join(MASK_DIR, period_s, 'cover_4326.geojson')
    data = gpd.read_file(src_path)
    data_proj = data.copy()
    data_proj['geometry'] = data_proj['geometry'].to_crs(epsg=4326)
    data_proj.to_file(dst_path)

    logger.info("Load mask to DB")
    ds = DataSource(dst_path)
    polys = []
    for x in range(0, len(ds[0]) - 1):
        geom = shapely.wkt.loads(ds[0][x].geom.wkt)
        polys.append(geom)
    multipoly = unary_union(polys)
    Mask.objects.update_or_create(
        period=period,
        mask_type='loss',
        defaults=dict(geom=GEOSGeometry(multipoly.wkt)))


def generate_measurements(period):
    logger.info("Generate measurements for each scope")

    for scope in Scope.objects.all():
        mask = Mask.objects.filter(period=period, mask_type='loss').first()

        # TODO Optimize: use JOINs with Scope and Mask instead of building the shape WKT
        query = """
            SELECT ST_Area(a.int) AS area,
                   ST_Area(ST_Transform(ST_GeomFromText('{wkt_scope}', 4326), {srid})) as scope_area
            FROM (
                SELECT ST_Intersection(
                    ST_Transform(ST_GeomFromText('{wkt_scope}', 4326), {srid}),
                    ST_Transform(ST_GeomFromText('{wkt_mask}', 4326), {srid})) AS int) a;
            """.format(wkt_scope=scope.geom.wkt,
                       wkt_mask=mask.geom.wkt,
                       srid=32718)

        try:
            with connection.cursor() as cursor:
                cursor.execute(query)
                res = cursor.fetchall()
                area, scope_area = res[0]

            measurement, created = CoverageMeasurement.objects.update_or_create(
                date_from=period.date_from,
                date_to=period.date_to,
                scope=scope,
                defaults=dict(area=area, perc_area=area / scope_area))
            if created:
                logger.info(f"New measurement: {measurement}")
        except DatabaseError as err:
            logger.error(err)
            logger.info(
                f"An error occurred! Skipping measurement for scope {scope.id}..."
            )


def hex_to_dec_string(value):
    return np.array([int(value[i:j], 16) for i, j in [(0, 2), (2, 4), (4, 6)]],
                    np.uint8)
