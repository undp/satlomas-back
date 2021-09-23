import logging
import multiprocessing as mp
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

from multiprocessing.pool import ThreadPool
from functools import partial
import numpy as np
import rasterio
from django.conf import settings
from django.contrib.gis.gdal import GDALRaster
from django.contrib.gis.geos import GEOSGeometry
from django.core.files import File
from django.db import DatabaseError, connection, transaction
from eo_sensors.models import CoverageMask, CoverageMeasurement, Raster
from rasterio.windows import Window
from satlomasproc.chips.utils import reproject_shape
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
    rgb_raster_path,
    cov_raster_path=None,
    kinds_per_value=None,
    simplify=None,
    *,
    source,
    slug,
    date,
    name,
    zoom_range,
):
    raster, _ = Raster.objects.update_or_create(
        source=source, date=date, slug=slug, defaults=dict(name=name)
    )

    # If raster already has a file, delete it
    if raster.file:
        raster.file.delete()

    # Store RGB raster on `file` field
    with open(rgb_raster_path, "rb") as f:
        raster.file.save(f"{slug}.tif", File(f, name=f"{slug}.tif"))

    # Generate tiles for map view
    create_raster_tiles(raster, levels=zoom_range, n_jobs=mp.cpu_count())

    # Create related CoverageMasks, if `cov_raster_path` was provided
    if cov_raster_path:
        masks = create_coverage_masks(
            raster, cov_raster_path=cov_raster_path, kinds_per_value=kinds_per_value
        )
        generate_measurements(masks, simplify=simplify)


def write_paletted_rgb_raster(src_path, dst_path, *, colormap):
    with rasterio.open(src_path) as src:
        profile = src.profile.copy()
        profile.update(count=4, dtype="uint8", compress="deflate", tiled=True)
        del profile["nodata"]

        os.makedirs(os.path.dirname(dst_path), exist_ok=True)

        with rasterio.open(dst_path, "w", **profile) as dst:
            for _, window in src.block_windows(1):
                img = src.read(1, window=window)

                new_img = np.zeros((img.shape[0], img.shape[1], 3), dtype=np.uint8)
                for i in range(len(colormap)):
                    if colormap[i]:
                        color = hex_to_dec_string(colormap[i])
                        new_img[img == (i + 1), :] = color
                mask = (img != 0).astype(np.uint8) * 255

                for i in range(new_img.shape[2]):
                    dst.write(new_img[:, :, i], i + 1, window=window)
                # Write alpha band
                dst.write(mask, 4, window=window)
    add_overviews(dst_path)


def add_overviews(src_path):
    logger.info("Add internal compressed overviews to %s", src_path)
    run_command(
        f"gdaladdo --config COMPRESS_OVERVIEW JPEG --config INTERLEAVE_OVERVIEW PIXEL {src_path} 2 4 8 16"
    )


def create_coverage_masks(raster, *, cov_raster_path, kinds_per_value):
    import geopandas as gpd
    from shapely.ops import unary_union

    with tempfile.TemporaryDirectory() as tmpdir:
        logger.info("Polygonize mask")
        geojson_path = os.path.join(tmpdir, "mask.geojson")
        run_command(
            '{gdal_bin_path}/gdal_polygonize.py {src} {dst} -b 1 -f "GeoJSON" DN'.format(
                gdal_bin_path=settings.GDAL_BIN_PATH,
                src=cov_raster_path,
                dst=geojson_path,
            )
        )

        logging.info("Reproject to epsg:4326")
        gdf = gpd.read_file(geojson_path)
        gdf["geometry"] = gdf["geometry"].to_crs(epsg=4326)

        logging.info("Group all features by kind")
        polys_per_kind = {}
        for _, row in gdf.iterrows():
            if not row["DN"]:
                continue
            dn = int(row["DN"])
            kind = kinds_per_value[dn]
            if kind not in polys_per_kind:
                polys_per_kind[kind] = []
            polys_per_kind[kind].append(row["geometry"])

        # Create a CoverageMask for each kind by merging all polygons into a
        # single multipolygon
        logging.info("Create CoverageMask for each kind")
        masks = []
        for kind, polys in polys_per_kind.items():
            geom = unary_union(polys)
            mask, _ = CoverageMask.objects.update_or_create(
                date=raster.date,
                source=raster.source,
                kind=kind,
                defaults=dict(geom=GEOSGeometry(geom.wkt), raster=raster),
            )
            masks.append(mask)

        return masks


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


def generate_measurements(coverage_masks, scopes=None, simplify=None):
    logger.info("Generate measurements for each scope")

    if not scopes:
        scopes = Scope.objects.all()

    with ThreadPool(mp.cpu_count()) as pool:
        worker = partial(
            _generate_measurements, coverage_masks=coverage_masks, simplify=simplify
        )
        pool.map(worker, scopes)


def _generate_measurements(scope, simplify=None, *, coverage_masks):
    logger.info(f"Scope: %s", scope)
    scope.geom.transform(32718)
    scope_area = scope.geom.area

    for mask in coverage_masks:
        mask.geom.transform(32718)
        mask_geom = mask.geom
        if simplify:
            mask_geom = mask_geom.simplify(3.0, preserve_topology=False)

        inter_geom = scope.geom.intersection(mask_geom)
        area = inter_geom.area

        measurement, created = CoverageMeasurement.objects.update_or_create(
            date=mask.date,
            kind=mask.kind,
            source=mask.source,
            scope=scope,
            defaults=dict(area=area, perc_area=area / scope_area),
        )
        if created:
            logger.info(f"New measurement: {measurement}")


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


def create_raster_tiles(raster, n_jobs=None, *, levels):
    gdal2tiles = settings.GDAL2TILES_BIN_PATH
    if not n_jobs:
        n_jobs = settings.GDAL2TILES_NUM_JOBS

    media_dir = settings.MEDIA_ROOT
    tiles_dir = os.path.join(media_dir, "tiles")

    src = raster.file.path
    dst = os.path.join(tiles_dir, raster.path())
    tmp_dst = os.path.join("/dev/shm", "tiles", raster.path())
    zoom_range = f"{levels[0]}-{levels[1]}"

    cmd = f"{gdal2tiles} --processes {n_jobs} -w none -n -z {zoom_range} {src} {tmp_dst}"

    logger.info("Delete %s", tmp_dst)
    if os.path.exists(tmp_dst):
        shutil.rmtree(tmp_dst, ignore_errors=True)
    run_command(cmd)
    logger.info("Move files from %s to %s", tmp_dst, os.path.dirname(dst[:-1]))
    if os.path.exists(dst):
        shutil.rmtree(dst, ignore_errors=True)
    shutil.move(tmp_dst, os.path.dirname(dst[:-1]))


def write_rgb_raster(func):
    def wrapper(*, src_path, dst_path):
        with rasterio.open(src_path) as src:
            img = src.read(1)
            profile = src.profile.copy()
        new_img = func(img)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        profile.update(count=new_img.shape[2], dtype=np.uint8)
        with rasterio.open(dst_path, "w", **profile) as dst:
            for i in range(new_img.shape[2]):
                dst.write(new_img[:, :, i], i + 1)

    return wrapper


def hex_to_dec_string(value):
    return np.array(
        [int(value[i:j], 16) for i, j in [(0, 2), (2, 4), (4, 6)]], np.uint8
    )
