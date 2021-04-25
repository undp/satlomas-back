import calendar
import fnmatch
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from glob import glob

import geopandas as gpd
import numpy as np
import rasterio
import shapely.wkt
from django.conf import settings
from django.contrib.gis.gdal import DataSource
from django.contrib.gis.geos import GEOSGeometry
from django.core.files import File
from django.db import DatabaseError, connection
from eo_sensors.models import CoverageMeasurement, Raster
from eo_sensors.tasks import APP_DATA_DIR, TASKS_DATA_DIR
from jobs.utils import job

from scopes.models import Scope
from shapely.ops import unary_union

from satlomasproc.modis_vi import get_modisfiles, extract_subdatasets_as_gtiffs


# Configure logger
logger = logging.getLogger(__name__)
out_handler = logging.StreamHandler(sys.stdout)
out_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
out_handler.setLevel(logging.INFO)
logger.addHandler(out_handler)
logger.setLevel(logging.INFO)

# Base directories
MODIS_VI_DATA_DIR = os.path.join(APP_DATA_DIR, "modis_vi")
MODIS_VI_TASKS_DATA_DIR = os.path.join(TASKS_DATA_DIR, "modis_vi")

# Files needed for tasks
EXTENT_PATH = os.path.join(MODIS_VI_DATA_DIR, "extent.geojson")
AOI_PATH = os.path.join(MODIS_VI_DATA_DIR, "aoi.geojson")
SRTM_DEM_PATH = os.path.join(MODIS_VI_DATA_DIR, "srtm_dem.tif")

# Directories used in the processing pipeline
MVI_RAW_DIR = os.path.join(MODIS_VI_TASKS_DATA_DIR, "raw")
MVI_TIF_DIR = os.path.join(MODIS_VI_TASKS_DATA_DIR, "tif")
MVI_CLIP_DIR = os.path.join(MODIS_VI_TASKS_DATA_DIR, "clip")
MVI_MASK_DIR = os.path.join(MODIS_VI_TASKS_DATA_DIR, "masks")
MVI_RESULTS_DIR = os.path.join(MODIS_VI_TASKS_DATA_DIR, "results")
# MVI_RGB_DIR = os.path.join(MODIS_VI_TASKS_DATA_DIR, 'rgb')

# MODIS
HEADERS = {"User-Agent": "get_modis Python 3"}
CHUNKS = 65536

MODIS_PLATFORM = "MOLA"
MODIS_PRODUCT = "MYD13Q1.006"
H_PERU = "10"
V_PERU = "10"

LOMAS_MIN = 200
LOMAS_MAX = 1800
FACTOR_ESCALA = 0.0001
UMBRAL_NDVI = 0.2
THRESHOLD = UMBRAL_NDVI / FACTOR_ESCALA

# def process_all(period):
#     download_and_process(period)
#     create_rgb_rasters(period)
#     create_masks(period)
#     generate_measurements(period)


@job("processing")
def process_period(job):
    date_from = datetime.strptime(job.kwargs["date_from"], "%Y-%m-%d")
    date_to = datetime.strptime(job.kwargs["date_to"], "%Y-%m-%d")

    download_and_process(date_from, date_to)
    # create_rgb_rasters(date_from, date_to)
    # create_masks(date_from, date_to)
    # generate_measurements(date_from, date_to)


def download_and_process(date_from, date_to):
    year = date_to.year
    doy_begin = date_from.timetuple().tm_yday
    doy_end = date_to.timetuple().tm_yday

    os.makedirs(MVI_RAW_DIR, exist_ok=True)
    os.makedirs(MVI_TIF_DIR, exist_ok=True)

    logger.info("Download MODIS hdf files")
    tile = "h{}v{}".format(H_PERU, V_PERU)
    modis_filenames = get_modisfiles(
        settings.MODIS_USER,
        settings.MODIS_PASS,
        MODIS_PLATFORM,
        MODIS_PRODUCT,
        year,
        tile,
        proxy=None,
        doy_start=doy_begin,
        doy_end=doy_end,
        out_dir=MVI_RAW_DIR,
        verbose=True,
        ruff=False,
        get_xml=False,
    )

    if not modis_filenames:
        logger.error("No MODIS files for this period!")
        return

    extract_subdatasets_as_gtiffs(modis_filenames, MVI_TIF_DIR)

    logger.info("Clip SRTM to extent")
    srtm_clipped_path = os.path.join(MODIS_VI_TASKS_DATA_DIR, "srtm_dem_clipped.tif")
    if not os.path.exists(srtm_clipped_path):
        run_command(
            "{gdal_bin_path}/gdalwarp -of GTiff -cutline {aoi} -crop_to_cutline {src} {dst}".format(
                gdal_bin_path=settings.GDAL_BIN_PATH,
                aoi=EXTENT_PATH,
                src=SRTM_DEM_PATH,
                dst=srtm_clipped_path,
            )
        )

    logger.info("Calculate SRTM mask")
    with rasterio.open(srtm_clipped_path) as srtm_src:
        srtm = srtm_src.read(1)
        lomas_mask = (srtm >= LOMAS_MIN) & (srtm <= LOMAS_MAX)

    logger.info("Clip NDVI to extent")
    os.makedirs(MVI_CLIP_DIR, exist_ok=True)
    name, _ = os.path.splitext(os.path.basename(modis_filenames[0]))
    ndvi_path = glob(os.path.join(MVI_TIF_DIR, f"{name}_ndvi.tif"))[0]
    ndvi_clipped_path = os.path.join(MVI_CLIP_DIR, os.path.basename(ndvi_path))
    if os.path.exists(ndvi_clipped_path):
        os.unlink(ndvi_clipped_path)
    run_command(
        "{gdal_bin_path}/gdalwarp -of GTiff -cutline {extent} -crop_to_cutline {src} {dst}".format(
            gdal_bin_path=settings.GDAL_BIN_PATH,
            extent=EXTENT_PATH,
            src=ndvi_path,
            dst=ndvi_clipped_path,
        )
    )

    logger.info("Superimpose clipped SRTM and NDVI rasters to align them")
    run_command(
        "{otb_bin_path}/otbcli_Superimpose -inr {inr} -inm {inm} -out {out}".format(
            otb_bin_path=settings.OTB_BIN_PATH,
            inr=srtm_clipped_path,
            inm=ndvi_clipped_path,
            out=ndvi_clipped_path,
        )
    )

    with rasterio.open(ndvi_clipped_path) as src:
        modis_ndvi = src.read(1)
        modis_meta = src.profile.copy()

    modis_meta["nodata"] = 0
    modis_meta["dtype"] = np.uint8

    logger.info("Build final vegetation mask")
    vegetacion_mask = modis_ndvi > THRESHOLD
    verde_mask = vegetacion_mask & lomas_mask
    verde = np.copy(modis_ndvi)
    verde[~verde_mask] = 0

    logger.info("Build scaled NDVI mask")
    verde_rango = np.copy(verde)
    verde_rango[(verde >= (0.2 / FACTOR_ESCALA)) & (verde < (0.4 / FACTOR_ESCALA))] = 1
    verde_rango[(verde >= (0.4 / FACTOR_ESCALA)) & (verde < (0.6 / FACTOR_ESCALA))] = 2
    verde_rango[(verde >= (0.6 / FACTOR_ESCALA)) & (verde < (0.8 / FACTOR_ESCALA))] = 3
    verde_rango[verde >= (0.8 / FACTOR_ESCALA)] = 4
    verde_rango[verde < 0] = 0
    verde_rango = verde_rango.astype(dtype=np.uint8)

    verde[verde_mask] = 1
    verde = verde.astype(dtype=np.uint8)

    period_s = f'{date_from.strftime("%Y%m")}-{date_to.strftime("%Y%m")}'

    logger.info("Write vegetation mask")
    os.makedirs(MVI_MASK_DIR, exist_ok=True)
    dst_name = os.path.join(MVI_MASK_DIR, "{}_vegetation_mask.tif".format(period_s))
    with rasterio.open(dst_name, "w", **modis_meta) as dst:
        dst.write(verde, 1)

    # Cloud mask
    logger.info("Clip pixel reliability raster to extent")
    name, _ = os.path.splitext(os.path.basename(modis_filenames[0]))
    pixelrel_path = glob(os.path.join(MVI_TIF_DIR, f"{name}_pixelrel.tif"))[0]
    pixelrel_clipped_path = os.path.join(MVI_CLIP_DIR, os.path.basename(pixelrel_path))
    if os.path.exists(pixelrel_clipped_path):
        os.unlink(pixelrel_clipped_path)
    run_command(
        "{gdal_bin_path}/gdalwarp -of GTiff -cutline {extent} -crop_to_cutline {src} {dst}".format(
            gdal_bin_path=settings.GDAL_BIN_PATH,
            extent=EXTENT_PATH,
            src=pixelrel_path,
            dst=pixelrel_clipped_path,
        )
    )

    logger.info("Superimpose pixel rel raster to SRTM raster")
    run_command(
        "{otb_bin_path}/otbcli_Superimpose -inr {inr} -inm {inm} -out {out}".format(
            otb_bin_path=settings.OTB_BIN_PATH,
            inr=srtm_clipped_path,
            inm=pixelrel_clipped_path,
            out=pixelrel_clipped_path,
        )
    )

    logger.info("Build cloud mask from pixel reliability raster")
    with rasterio.open(pixelrel_clipped_path) as cloud_src:
        clouds = cloud_src.read(1)

    # In clouds 2 is snow/ice and 3 are clouds, and -1 is not processed data
    cloud_mask = np.copy(clouds)
    cloud_mask[(clouds == 2) | (clouds == 3) | (clouds == -1)] = 1
    cloud_mask[(clouds != 2) & (clouds != 3)] = 0
    cloud_mask = cloud_mask.astype(np.uint8)

    cloud_mask_path = os.path.join(MVI_MASK_DIR, "{}_cloud_mask.tif".format(period_s))
    with rasterio.open(cloud_mask_path, "w", **modis_meta) as dst:
        dst.write(cloud_mask, 1)

    vegetation_range_path = os.path.join(
        MVI_MASK_DIR, "{}_vegetation_range.tif".format(period_s)
    )
    with rasterio.open(vegetation_range_path, "w", **modis_meta) as dst:
        dst.write(verde_rango, 1)

    logger.info("Create a mask with data from vegetation and clouds")
    verde[cloud_mask == 1] = 2
    veg_cloud_mask_path = os.path.join(
        MVI_MASK_DIR, "{}_vegetation_cloud_mask.tif".format(period_s)
    )
    with rasterio.open(veg_cloud_mask_path, "w", **modis_meta) as dst:
        dst.write(verde, 1)

    # Clip to AOI both vegetation_cloud_mask and vegetaion_range into RESULTS_DIR
    clip_with_aoi(veg_cloud_mask_path)
    clip_with_aoi(vegetation_range_path)

    clean_temp_files()


def clip_with_aoi(src):
    dst = os.path.join(MVI_RESULTS_DIR, os.path.basename(src))
    logger.info("Clip %s with AOI to %s", src, dst)

    os.makedirs(MVI_RESULTS_DIR, exist_ok=True)
    if not os.path.exists(dst):
        run_command(
            "{gdal_bin_path}/gdalwarp -of GTiff -cutline {aoi} -crop_to_cutline {src} {dst}".format(
                gdal_bin_path=settings.GDAL_BIN_PATH, aoi=AOI_PATH, src=src, dst=dst
            )
        )


def create_rgb_rasters(period):
    period_s = "{dfrom}-{dto}".format(
        dfrom=period.date_from.strftime("%Y%m"), dto=period.date_to.strftime("%Y%m")
    )

    src_path = os.path.join(MVI_MASK_DIR, f"{period_s}_vegetation_range.tif")
    dst_path = os.path.join(MVI_RGB_DIR, f"{period_s}_vegetation_range.tif")
    logger.info("Build RGB vegetation raster")
    write_vegetation_range_rgb_raster(src_path=src_path, dst_path=dst_path)
    raster, _ = Raster.objects.update_or_create(
        period=period, slug="ndvi", defaults=dict(name="NDVI")
    )
    with open(dst_path, "rb") as f:
        if raster.file:
            raster.file.delete()
        raster.file.save(f"ndvi.tif", File(f, name="ndvi.tif"))

    src_path = os.path.join(MVI_MASK_DIR, f"{period_s}_vegetation_mask.tif")
    dst_path = os.path.join(MVI_RGB_DIR, f"{period_s}_vegetation_mask.tif")
    logger.info("Build RGB vegetation mask raster")
    write_vegetation_mask_rgb_raster(src_path=src_path, dst_path=dst_path)
    raster, _ = Raster.objects.update_or_create(
        period=period, slug="vegetation", defaults=dict(name="Vegetation mask")
    )
    with open(dst_path, "rb") as f:
        if raster.file:
            raster.file.delete()
        raster.file.save(f"vegetation.tif", File(f))

    src_path = os.path.join(MVI_MASK_DIR, f"{period_s}_cloud_mask.tif")
    dst_path = os.path.join(MVI_RGB_DIR, f"{period_s}_cloud_mask.tif")
    logger.info("Build RGB cloud mask raster")
    write_cloud_mask_rgb_raster(src_path=src_path, dst_path=dst_path)
    raster, _ = Raster.objects.update_or_create(
        period=period, slug="cloud", defaults=dict(name="Cloud mask")
    )
    with open(dst_path, "rb") as f:
        if raster.file:
            raster.file.delete()
        raster.file.save(f"cloud.tif", File(f))


def write_rgb_raster(func):
    def wrapper(*, src_path, dst_path):
        with rasterio.open(src_path) as src:
            img = src.read(1)
            profile = src.profile.copy()
        new_img = func(img)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        profile.update(count=3, dtype=np.uint8)
        with rasterio.open(dst_path, "w", **profile) as dst:
            for i in range(new_img.shape[2]):
                dst.write(new_img[:, :, i], i + 1)

    return wrapper


def hex_to_dec_string(value):
    return np.array(
        [int(value[i:j], 16) for i, j in [(0, 2), (2, 4), (4, 6)]], np.uint8
    )


@write_rgb_raster
def write_vegetation_range_rgb_raster(img):
    colormap = ["1F6873", "1FA188", "70CF57", "FDE725"]
    new_img = np.zeros((img.shape[0], img.shape[1], 3), dtype=np.uint8)
    for i in range(len(colormap)):
        new_img[img == i + 1] = hex_to_dec_string(colormap[i])
    return new_img


@write_rgb_raster
def write_cloud_mask_rgb_raster(img):
    colormap = ["30a7ff"]
    new_img = np.zeros((img.shape[0], img.shape[1], 3), dtype=np.uint8)
    for i in range(len(colormap)):
        new_img[img == i + 1] = hex_to_dec_string(colormap[i])
    return new_img


@write_rgb_raster
def write_vegetation_mask_rgb_raster(img):
    colormap = ["149c00"]
    new_img = np.zeros((img.shape[0], img.shape[1], 3), dtype=np.uint8)
    for i in range(len(colormap)):
        new_img[img == i + 1] = hex_to_dec_string(colormap[i])
    return new_img


def create_masks(period):
    period_s = "{dfrom}-{dto}".format(
        dfrom=period.date_from.strftime("%Y%m"), dto=period.date_to.strftime("%Y%m")
    )

    logger.info("Polygonize mask")
    src_path = os.path.join(
        MVI_MASK_DIR, "{}_vegetation_cloud_mask.tif".format(period_s)
    )
    dst_path = os.path.join(
        MVI_MASK_DIR, "{}_vegetation_cloud_mask.geojson".format(period_s)
    )
    run_command(
        '{gdal_bin_path}/gdal_polygonize.py {src} {dst} -b 1 -f "GeoJSON" DN'.format(
            gdal_bin_path=settings.GDAL_BIN_PATH, src=src_path, dst=dst_path
        )
    )

    logging.info("Reproject to epsg:4326")
    data = gpd.read_file(dst_path)
    data_proj = data.copy()
    data_proj["geometry"] = data_proj["geometry"].to_crs(epsg=4326)
    data_proj.to_file(dst_path)

    logger.info("Load vegetation mask to DB")
    create_vegetation_masks(dst_path, period)


def create_vegetation_masks(geojson_path, period):
    ds = DataSource(geojson_path)
    vegetation_polys = []
    clouds_polys = []
    for x in range(0, len(ds[0]) - 1):
        geom = shapely.wkt.loads(ds[0][x].geom.wkt)
        if str(ds[0][x]["DN"]) == "1":
            vegetation_polys.append(geom)
        elif str(ds[0][x]["DN"]) == "2":
            clouds_polys.append(geom)
        else:
            pass
    vegetation_mp = unary_union(vegetation_polys)
    clouds_mp = unary_union(clouds_polys)

    Mask.objects.update_or_create(
        period=period,
        mask_type="ndvi",
        defaults=dict(geom=GEOSGeometry(vegetation_mp.wkt)),
    )
    Mask.objects.update_or_create(
        period=period,
        mask_type="cloud",
        defaults=dict(geom=GEOSGeometry(clouds_mp.wkt)),
    )


def generate_measurements(period):
    logger.info("Generate measurements for each scope")

    for scope in Scope.objects.all():
        mask = Mask.objects.filter(period=period, mask_type="ndvi").first()

        # TODO Optimize: use JOINs with Scope and Mask instead of building the shape WKT
        query = """
            SELECT ST_Area(a.int) AS area,
                   ST_Area(ST_Transform(ST_GeomFromText('{wkt_scope}', 4326), {srid})) as scope_area
            FROM (
                SELECT ST_Intersection(
                    ST_Transform(ST_GeomFromText('{wkt_scope}', 4326), {srid}),
                    ST_Transform(ST_GeomFromText('{wkt_mask}', 4326), {srid})) AS int) a;
            """.format(
            wkt_scope=scope.geom.wkt, wkt_mask=mask.geom.wkt, srid=32718
        )

        try:
            with connection.cursor() as cursor:
                cursor.execute(query)
                res = cursor.fetchall()
                area, scope_area = res[0]

            measurement, created = CoverageMeasurement.objects.update_or_create(
                date_from=period.date_from,
                date_to=period.date_to,
                scope=scope,
                defaults=dict(area=area, perc_area=area / scope_area),
            )
            if created:
                logger.info(f"New measurement: {measurement}")
        except DatabaseError as err:
            logger.error(err)
            logger.info(
                f"An error occurred! Skipping measurement for scope {scope.id}..."
            )


def clean_temp_files():
    logger.info("Clean temporary files")
    shutil.rmtree(MVI_CLIP_DIR)
    shutil.rmtree(MVI_TIF_DIR)
    shutil.rmtree(MVI_MASK_DIR)
    # shutil.rmtree(MVI_RAW_DIR)
