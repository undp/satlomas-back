import logging
import os
import subprocess
import zipfile

import numpy as np
import rasterio
from django.core.files import File
from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from rasterio.windows import Window
from shapely.geometry import box
from skimage import exposure
from tqdm import tqdm

from lomas_changes.models import Raster

logger = logging.getLogger(__name__)


def run_subprocess(cmd):
    logger.info("Run: %s", cmd)
    subprocess.run(cmd, shell=True, check=True)


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
        profile.update(count=3,
                       dtype=np.uint8,
                       compress='deflate',
                       tiled=True,
                       nodata=0)
        height, width = src.shape[0], src.shape[1]
        if not bands:
            bands = range(1, src.count + 1)
        with rasterio.open(dst_path, 'w', **profile) as dst:
            windows = list(sliding_windows(1000, width, height))
            for window in tqdm(windows):
                img = np.dstack([src.read(b, window=window) for b in bands])
                new_img = np.dstack([
                    exposure.rescale_intensity(img[:, :, i],
                                               in_range=in_range[i],
                                               out_range=(1, 255)).astype(
                                                   np.uint8)
                    for i in range(img.shape[2])
                ])
                for i in range(3):
                    dst.write(new_img[:, :, i], i + 1, window=window)


def clip(src, dst, *, aoi):
    # Make sure directory exists, and if file exists, delete to overwrite
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        os.unlink(dst)

    logger.info("Clip raster %s to %s using %s as cutline", src, dst, aoi)
    gdalwarp_bin = f'{settings.GDAL_BIN_PATH}/gdalwarp'
    run_subprocess(
        f'{gdalwarp_bin} -of GTiff -co COMPRESS=DEFLATE -co TILED=YES -cutline {aoi} -crop_to_cutline {src} {dst}'
    )


def rescale_byte(src, dst, *, in_range):
    # Make sure directory exists, and if file exists, delete to overwrite
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        os.unlink(dst)

    logger.info("Rescale raster %s to %s with input range %s", src, dst,
                in_range)
    gdal_translate_bin = f'{settings.GDAL_BIN_PATH}/gdal_translate'
    run_subprocess(f"{gdal_translate_bin} -of GTiff -ot Byte " \
        f"-scale {' '.join(str(v) for v in in_range)} 1 255 -a_nodata 0 " \
        f"-co COMPRESS=DEFLATE -co TILED=YES " \
        f"{src} {dst}")


def create_raster(rgb_raster_path, cov_raster_path=None, *, slug, date, name):
    raster, _ = Raster.objects.update_or_create(date=date,
                                                slug=slug,
                                                defaults=dict(name=name))

    # Validate RGB raster
    with rasterio.open(rgb_raster_path) as src:
        if src.count != 3:
            raise RuntimeError("Must have 3 bands, but has %d" % (src.count))
        if src.crs != 'epsg:32718':
            raise RuntimeError("CRS must be epsg:32718, but was %s" % (src.crs))
        if any(np.dtype(dt) != rasterio.uint8 for dt in src.dtypes):
            raise RuntimeError("dtype should be uint8, but was %s" %
                               (src.profile['dtype']))

    # If raster already has a file, delete it
    if raster.file:
        raster.file.delete()

    # Store RGB raster on `file` field
    with open(rgb_raster_path, 'rb') as f:
        raster.file.save(f'{slug}.tif', File(f, name=f'{slug}.tif'))

    # Create a related CoverageRaster, if `cov_raster_path` was provided
    if cov_raster_path:
        coverage_raster, _ = CoverageRaster.objects.update_or_create(
            raster=raster)
        with rasterio.open(cov_raster_path) as src:
            coverage_raster.cov_raster = src.read()
        coverage_raster.save()


def write_paletted_rgb_raster(src_path, dst_path, *, colormap):
    with rasterio.open(src_path) as src:
        img = src.read(1)
        profile = src.profile.copy()

    new_img = np.zeros((img.shape[0], img.shape[1], 3), dtype=np.uint8)
    for i in range(len(colormap)):
        new_img[img == i + 1] = hex_to_dec_string(colormap[i])

    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    profile.update(count=3,
                   dtype=np.uint8,
                   nodata=0,
                   compress='deflate',
                   tiled=True)
    with rasterio.open(dst_path, 'w', **profile) as dst:
        for i in range(new_img.shape[2]):
            dst.write(new_img[:, :, i], i + 1)


def hex_to_dec_string(value):
    return np.array([int(value[i:j], 16) for i, j in [(0, 2), (2, 4), (4, 6)]],
                    np.uint8)
