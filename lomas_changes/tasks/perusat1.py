import logging
import os
import sys
import tempfile
from datetime import datetime

import django_rq
from django.conf import settings
from django.contrib.gis.gdal import DataSource
from django.contrib.gis.geos import GEOSGeometry
from jobs.models import Job
from jobs.utils import enqueue_job, job
from lomas_changes.clients import SFTPClient
from lomas_changes.models import Mask, Object, Raster
from lomas_changes.utils import unzip

# Configure logger
logger = logging.getLogger(__name__)
out_handler = logging.StreamHandler(sys.stdout)
out_handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
out_handler.setLevel(logging.INFO)
logger.addHandler(out_handler)
logger.setLevel(logging.INFO)

# Base directory
DATA_DIR = os.path.join(settings.DATA_DIR, 'lomas_changes', 'ps1')
# "raw" directory contains uncompressed Level-1 PeruSat-1 scenes
RAW_DIR = os.path.join(DATA_DIR, 'raw')
# "proc" directory contains pansharpened scenes (result of perusatproc)
PROC_DIR = os.path.join(DATA_DIR, 'proc')
# "rgb" directory contains RGB 8-bit images to be predicted and loaded
RGB_DIR = os.path.join(DATA_DIR, 'rgb')
# "results" directory contains binary rasters with results of model prediction
RESULTS_DIR = os.path.join(DATA_DIR, 'results')


@job('processing')
def import_scene_from_sftp(job):
    """Connects to an SFTP server and downloads a scene"""

    sftp_conn_info = job.kwargs['sftp_conn_info']
    filepath = job.kwargs['file']

    client = SFTPClient(**sftp_conn_info)
    with tempfile.TemporaryDirectory() as tmpdir:
        basename = os.path.basename(filepath)
        id_s = datetime.now().strftime('%YYYY%m%d_%H%M%S')
        scene_dir = os.path.join(RAW_DIR, id_s)

        # Download file and extract to RAW_DIR
        dst = os.path.join(tmpdir, basename)
        logger.info("Download %s to %s", filepath, dst)
        client.get(filepath, dst)
        logger.info("Unzip %s into %s", dst, scene_dir)
        unzip(dst, scene_dir)

        # Next job: process new scene
        enqueue_job('lomas_changes.tasks.perusat1.process_scene',
                    scene_dir=scene_dir,
                    queue='processing')


@job('processing')
def process_scene(job):
    raw_scene_dir = job.kwargs['scene_dir']

    from perusatproc.console.process import process_product

    basename = os.path.basename(raw_scene_dir)
    proc_scene_dir = os.path.join(PROC_DIR, basename)

    logger.info("Process %s into %s", raw_scene_dir, proc_scene_dir)
    process_product(raw_scene_dir, proc_scene_dir)

    # TODO: Create RGB image from pansharpened image
    #rgb_scene_dir = os.path.join(RGB_DIR, basename)
    # TODO: Load RGB image
    # TODO: Predict over RGB image
    # TODO: Postprocess results
    # TODO: Load results (raster and mask)


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
    import geopandas as gpd
    import shapely.wkt
    from shapely.ops import unary_union

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
