import logging
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

import numpy as np
import rasterio
from django.conf import settings
from django.contrib.gis.gdal import GDALRaster
from django.contrib.gis.geos import GEOSGeometry
from django.core.files import File
from django.db import DatabaseError, connection, transaction
from eo_sensors.models import CoverageMeasurement, CoverageRaster, Raster
from rasterio.windows import Window
from scopes.models import Scope
from shapely.geometry import box
from skimage import exposure
from tqdm import tqdm

# Configure logger
logger = logging.getLogger(__name__)
out_handler = logging.StreamHandler(sys.stdout)
out_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
out_handler.setLevel(logging.INFO)
logger.addHandler(out_handler)
logger.setLevel(logging.INFO)


def run_command(cmd):
    logger.info("Run command: %s", cmd)
    subprocess.run(cmd, shell=True, check=True)


def run_otb_command(cmd, cwd=None):
    logger.info("Run command: %s", cmd)
    otb_profile_path = settings.OTB_PROFILE_PATH
    if otb_profile_path:
        logger.info("Use OTB profile environment at %s", otb_profile_path)
        cmd = f"/bin/bash -c 'source {otb_profile_path}; {cmd}'"
    subprocess.run(cmd, shell=True, check=True, cwd=cwd)


def unzip(zip_name, extract_folder=None, delete_zip=True):
    if extract_folder is None:
        extract_folder = os.path.dirname(zip_name)
    resultzip = zipfile.ZipFile(zip_name)
    resultzip.extractall(extract_folder)
    resultzip.close()
    if delete_zip:
        os.remove(zip_name)


def sliding_windows(size, width, height):
    """Slide a window of +size+ pixels"""
    for i in range(0, height, size):
        for j in range(0, width, size):
            yield Window(j, i, min(width - j, size), min(height - i, size))


# TODO: check if used, if not, delete
def write_rgb_raster(bands=[], *, src_path, dst_path, in_range):
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    with rasterio.open(src_path) as src:
        profile = src.profile.copy()
        profile.update(
            count=3, dtype=np.uint8, compress="deflate", tiled=True, nodata=0
        )
        height, width = src.shape[0], src.shape[1]
        if not bands:
            bands = range(1, src.count + 1)
        with rasterio.open(dst_path, "w", **profile) as dst:
            windows = list(sliding_windows(1000, width, height))
            for window in tqdm(windows):
                img = np.dstack([src.read(b, window=window) for b in bands])
                new_img = np.dstack(
                    [
                        exposure.rescale_intensity(
                            img[:, :, i], in_range=in_range[i], out_range=(1, 255)
                        ).astype(np.uint8)
                        for i in range(img.shape[2])
                    ]
                )
                for i in range(3):
                    dst.write(new_img[:, :, i], i + 1, window=window)


def clip(src, dst, *, aoi):
    # Make sure directory exists, and if file exists, delete to overwrite
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        os.unlink(dst)

    logger.info("Clip raster %s to %s using %s as cutline", src, dst, aoi)
    gdalwarp_bin = f"{settings.GDAL_BIN_PATH}/gdalwarp"
    run_command(
        f"{gdalwarp_bin} -of GTiff -co COMPRESS=DEFLATE -co TILED=YES -cutline {aoi} -crop_to_cutline {src} {dst}"
    )


def rescale_byte(src, dst, *, in_range):
    # Make sure directory exists, and if file exists, delete to overwrite
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        os.unlink(dst)

    logger.info("Rescale raster %s to %s with input range %s", src, dst, in_range)
    gdal_translate_bin = f"{settings.GDAL_BIN_PATH}/gdal_translate"
    run_command(
        f"{gdal_translate_bin} -of GTiff -ot Byte "
        f"-scale {' '.join(str(v) for v in in_range)} 1 255 -a_nodata 0 "
        f"-co COMPRESS=DEFLATE -co TILED=YES "
        f"{src} {dst}"
    )


def create_raster(
    rgb_raster_path, cov_raster_path=None, *, slug, date, name, zoom_range
):
    raster, _ = Raster.objects.update_or_create(
        date=date, slug=slug, defaults=dict(name=name)
    )

    # Validate RGB raster
    with rasterio.open(rgb_raster_path) as src:
        if src.count != 4:
            raise RuntimeError(
                "Must have 4 bands (RGB + alpha band), but has %d" % (src.count)
            )
        if src.crs != "epsg:32718":
            raise RuntimeError("CRS must be epsg:32718, but was %s" % (src.crs))
        if any(np.dtype(dt) != rasterio.uint8 for dt in src.dtypes):
            raise RuntimeError(
                "dtype should be uint8, but was %s" % (src.profile["dtype"])
            )

    # If raster already has a file, delete it
    if raster.file:
        raster.file.delete()

    # Store RGB raster on `file` field
    with open(rgb_raster_path, "rb") as f:
        raster.file.save(f"{slug}.tif", File(f, name=f"{slug}.tif"))

    # Create a related CoverageRaster, if `cov_raster_path` was provided
    if cov_raster_path:
        cov_rast = GDALRaster(cov_raster_path, write=True)
        CoverageRaster.objects.update_or_create(cov_rast=cov_rast, raster=raster)

    # Generate tiles for map view
    generate_raster_tiles(raster, zoom_range=zoom_range)


def write_paletted_rgb_raster(src_path, dst_path, *, colormap):
    with rasterio.open(src_path) as src:
        img = src.read(1)
        profile = src.profile.copy()

    new_img = np.zeros((img.shape[0], img.shape[1], 3), dtype=np.uint8)
    for i in range(len(colormap)):
        color = hex_to_dec_string(colormap[i])
        new_img[img == (i + 1), :] = color
    mask = (img != 0).astype(np.uint8) * 255

    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    profile.update(count=4, dtype="uint8", compress="deflate", tiled=True)
    del profile["nodata"]
    with rasterio.open(dst_path, "w", **profile) as dst:
        for i in range(new_img.shape[2]):
            dst.write(new_img[:, :, i], i + 1)
        # Write alpha band
        dst.write(mask, 4)


def hex_to_dec_string(value):
    return np.array(
        [int(value[i:j], 16) for i, j in [(0, 2), (2, 4), (4, 6)]], np.uint8
    )


def select_sql(query, *params):
    import time

    with connection.cursor() as cursor:
        start = time.time()
        cursor.execute(query, params)
        res = cursor.fetchall()
        end = time.time()
        logger.info("Took %f to execute SQL: %s", end - start, query)
        return res


def generate_measurements(*, date, raster_type, kinds_per_value):
    logger.info("Generate measurements for raster '%s' at date %s")

    for scope in Scope.objects.all():
        # coverage_raster = CoverageRaster.objects.filter(
        #     date=date, raster__slug=raster_type).first()

        # FIXME Join with scopes directly instead of passing scope geom as WKT
        try:
            res = select_sql(
                """
                WITH reprojected_scope AS (
                    SELECT ST_Transform(ST_GeomFromText(%s, 4326), 32718) AS scope_geom
                ), area_scope AS (
                    SELECT ST_Area(scope_geom) AS scope_area
                    FROM reprojected_scope
                ), clipped_raster AS (
                    SELECT ST_Clip(cr.cov_rast, 1, scope_geom, true) AS rast
                    FROM reprojected_scope, eo_sensors_coverageraster cr
                    INNER JOIN eo_sensors_raster r ON r.id = cr.raster_id
                    WHERE r.slug = %s AND r.date = %s
                ), count_agg AS (
                    SELECT CAST(ST_CountAgg(rast, 1, false) AS double precision) AS total
                    FROM clipped_raster
                ), value_count AS (
                    SELECT (ST_ValueCount(rast)).*
                    FROM clipped_raster
                )
                SELECT value_count.value, value_count.count / total, scope_area
                FROM clipped_raster, count_agg, value_count, area_scope
            """,
                scope.geom.wkt,
                raster_type,
                date,
            )

            if res:
                for value, ratio, scope_area in res:
                    kind = kinds_per_value[value]
                    area = scope_area * ratio
                    measurement, created = CoverageMeasurement.objects.update_or_create(
                        date=date,
                        scope=scope,
                        kind=kind,
                        defaults=dict(area=area, perc_area=ratio),
                    )
                    if created:
                        logger.info(f"New measurement: {measurement}")

        except DatabaseError as err:
            logger.error(err)
            logger.info(
                f"An error occurred! Skipping measurement for scope {scope.id}..."
            )


# @deprecated?
def generate_raster_tiles(raster, zoom_range=(4, 18)):
    # First, download file from storage to temporary local file
    with tempfile.NamedTemporaryFile() as tmpfile:
        shutil.copyfileobj(raster.file, tmpfile)
        src = tmpfile.name

        from_zoom, to_zoom = zoom_range
        zoom_range = "{}-{}".format(from_zoom, to_zoom)

        # Create destination directory
        tiles_dir = os.path.join(settings.TILES_DIR, raster.path)
        os.makedirs(tiles_dir, exist_ok=True)

        # Use gdal2tiles to generate raster tiles
        cmd = "{gdal2tiles} --processes {n_jobs} -w none -n -z {zoom_range} {src} {dst}".format(
            gdal2tiles=settings.GDAL2TILES_BIN_PATH,
            n_jobs=settings.GDAL2TILES_NUM_JOBS,
            zoom_range=zoom_range,
            src=tmpfile.name,
            dst=tiles_dir,
        )
        run_command(cmd)


def create_raster_tiles(raster, *, levels):
    gdal2tiles = settings.GDAL2TILES_BIN_PATH
    n_jobs = settings.GDAL2TILES_NUM_JOBS
    media_dir = settings.MEDIA_ROOT
    tiles_dir = os.path.join(media_dir, "tiles")

    src = raster.file.path
    dst = os.path.join(tiles_dir, raster.path())
    zoom_range = f"{levels[0]}-{levels[1]}"

    cmd = f"{gdal2tiles} --processes {n_jobs} -w none -n -z {zoom_range} {src} {dst}"

    # Make sure output directory does not exist
    if os.path.exists(dst):
        shutil.rmtree(dst)

    run_command(cmd)