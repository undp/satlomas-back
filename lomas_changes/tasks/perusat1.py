import logging
import os
import sys
import tempfile
from datetime import datetime

import geopandas as gpd
import shapely.wkt
from django.conf import settings
from django.contrib.gis.gdal import DataSource
from django.contrib.gis.geos import GEOSGeometry
from django_rq import job
from jobs.utils import enqueue_processing_job
from lomas_changes.clients import SFTPClient
from lomas_changes.models import Mask, Object, Raster
from lomas_changes.utils import unzip
from shapely.ops import unary_union

# Configure logger
logger = logging.getLogger(__name__)
out_handler = logging.StreamHandler(sys.stdout)
out_handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
out_handler.setLevel(logging.INFO)
logger.addHandler(out_handler)
logger.setLevel(logging.INFO)

DATA_DIR = os.path.join(settings.BASE_DIR, 'data', 'lomas_changes', 'ps1')
RAW_DIR = os.path.join(DATA_DIR, 'raw')
RESULTS_DIR = os.path.join(DATA_DIR, 'results')
IMAGE_DIR = os.path.join(DATA_DIR, 'image')
RGB_DIR = os.path.join(DATA_DIR, 'rgb')


@job('process')
def import_scene_from_sftp(sftp_conn_info, filepath):
    """Connects to an SFTP server and downloads a scene"""

    client = SFTPClient(**sftp_conn_info)
    with tempfile.TemporaryDirectory() as tmpdir:
        basename = os.path.basename(filepath)
        id_s = datetime.now().strftime('%YYYY%m%d_%H%M%S')
        scene_dir = os.path.join(RAW_DIR, id_s)

        # Download file and extract to RAW_DIR
        dst = os.path.join(tmpdir, basename)
        client.get(filepath, dst)
        unzip(dst, scene_dir)

        # Process new scene
        enqueue_processing_job(process_scene, scene_dir)


@job('process')
def process_scene(scene_dir):
    # TODO
    # call perusat_process
    pass


def load_data(period, product_id):
    #create_rgb_rasters(period, product_id)
    load_raster(period, product_id)
    load_mask_and_objects(period, product_id)


def load_raster(period, product_id):
    logger.info(f"Load {product_id} raster")
    Raster.objects.update_or_create(period=period,
                                    slug='ps1',
                                    defaults=dict(name=product_id))


def load_mask_and_objects(period, product_id):
    logging.info("Reproject to epsg:4326")
    src_path = os.path.join(RESULTS_DIR, product_id, 'objects.geojson')
    dst_path = os.path.join(RESULTS_DIR, product_id, 'objects_4326.geojson')
    data = gpd.read_file(src_path)
    data_proj = data.copy()
    data_proj['geometry'] = data_proj['geometry'].to_crs(epsg=4326)
    data_proj.to_file(dst_path)

    logger.info("Load roofs mask to DB")
    ds = DataSource(dst_path)
    polys = []
    for x in range(0, len(ds[0]) - 1):
        geom = shapely.wkt.loads(ds[0][x].geom.wkt)
        polys.append(geom)
    multipoly = unary_union(polys)
    Mask.objects.update_or_create(
        period=period,
        mask_type='roofs',
        defaults=dict(geom=GEOSGeometry(multipoly.wkt)))

    Object.objects.filter(period=period).delete()
    for poly in polys:
        Object.objects.create(period=period,
                              object_type="roof",
                              geom=GEOSGeometry(poly.wkt))
