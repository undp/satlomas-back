import json
import logging
import os
import shutil
import subprocess
import sys
from glob import glob
from pathlib import Path
from zipfile import ZipFile

from django.conf import settings
from django.core.files import File
from sentinelsat.sentinel import SentinelAPI, geojson_to_wkt, read_geojson

import lomas_changes
from lomas_changes.models import Raster
from lomas_changes.utils import (get_raster_extent, run_subprocess, unzip,
                                 write_rgb_raster)

APPDIR = os.path.dirname(lomas_changes.__file__)

RESULTS_PATH = os.path.join(settings.BASE_DIR, 'data', 'images', 'results')
RGB_PATH = os.path.join(settings.BASE_DIR, 'data', 'images', 'rgb')

S2_BASE_DIR = os.path.join(settings.BASE_DIR, 'data', 'images', 's2')
S2_L1C_PATH = os.path.join(S2_BASE_DIR, 'l1c')
S2_L2A_PATH = os.path.join(S2_BASE_DIR, 'l2a')

AOI_PATH = os.path.join(APPDIR, 'data', 'extent.geojson')
AOI_UTM_PATH = os.path.join(APPDIR, 'data', 'extent_utm.geojson')

# Configure logger
logger = logging.getLogger(__name__)
out_handler = logging.StreamHandler(sys.stdout)
out_handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
out_handler.setLevel(logging.INFO)
logger.addHandler(out_handler)
logger.setLevel(logging.INFO)


def process_all(period):
    download_scenes(period)
    create_rgb_rasters(period)


def download_scenes(period):
    date_from = period.date_from
    date_to = period.date_to

    period_s = '{dfrom}_{dto}'.format(dfrom=period.date_from.strftime("%Y%m"),
                                      dto=period.date_to.strftime("%Y%m"))

    # Check if result has already been done
    scene_filename = f's2_{period_s}*.tif'
    scene_path = os.path.join(RESULTS_PATH, scene_filename)
    if len(glob(scene_path)) == 2:
        print(
            "Sentinel-2 mosaic for period {}-{} already done:".format(
                date_from, date_to), scene_path)
        return

    if not settings.SCIHUB_USER or not settings.SCIHUB_PASS:
        raise "SCIHUB_USER and/or SCIHUB_PASS are not set. " + \
              "Please read the Configuration section on README."

    api = SentinelAPI(settings.SCIHUB_USER, settings.SCIHUB_PASS,
                      settings.SCIHUB_URL)

    # Search by polygon, time, and Hub query keywords
    footprint = geojson_to_wkt(
        read_geojson(os.path.join(APPDIR, 'data', 'extent.geojson')))

    products = api.query(footprint,
                         date=(date_from, date_to),
                         platformname='Sentinel-2',
                         cloudcoverpercentage=(0, 20))

    # Skip L2A products
    l2 = []
    for p in products:
        if 'MSIL2A' in products[p]['title']:
            l2.append(p)
    for p in l2:
        products.pop(p)

    for p in products:
        print(products[p]['title'])

    # Filter already downloaded products
    l1c_path = os.path.join(S2_L1C_PATH, period_s)
    os.makedirs(l1c_path, exist_ok=True)
    products_to_download = {
        k: v
        for k, v in products.items() if
        not os.path.exists(os.path.join(l1c_path, '{}.zip'.format(v['title'])))
    }

    # Download products
    api.download_all(products_to_download, directory_path=l1c_path)

    products = list(products.values())

    # Unzip
    for p in products:
        unzip_product(p, period_s)

    # Get the list of L1C products still to be processed to L2A
    l2a_path = os.path.join(S2_L2A_PATH, period_s)
    os.makedirs(l2a_path, exist_ok=True)
    l1c_can_prods = get_canonical_names(glob(os.path.join(l1c_path, '*.SAFE')))
    l2a_can_prods = get_canonical_names(glob(os.path.join(l2a_path, '*.SAFE')))
    missing_l1c_prods = [
        l1c_can_prods[k]
        for k in set(l1c_can_prods.keys()) - set(l2a_can_prods.keys())
    ]

    # Run s2m preprocess (sen2cor) on raw directory
    for p in missing_l1c_prods:
        sen2_preprocess(p, period_s)

    # Build mosaic
    mosaic_path = os.path.join(settings.IMAGES_PATH, 'mosaic', period_s)
    os.makedirs(mosaic_path, exist_ok=True)

    xmin, ymin, xmax, ymax = [
        260572.3994411753083114, 8620358.0515629947185516,
        324439.4877797830849886, 8720597.2414500378072262
    ]
    mosaic_name = 's2_{}{}_{}{}_mosaic'.format(date_from.year, date_from.month,
                                               date_to.year, date_to.month)

    for res in [10, 20]:
        cmd = "python3 {}/mosaic.py -te {} {} {} {} -e 32718 -res {} -n {} -v -o {} {}".format(
            settings.S2M_CLI_PATH, xmin, ymin, xmax, ymax, res, mosaic_name,
            mosaic_path, l2a_path)
        rv = os.system(cmd)
        if rv != 0:
            raise ValueError('s2m mosaic failed')

    generate_vegetation_indexes(mosaic_name, period_s)
    concatenate_results(mosaic_name, period_s)
    clip_results(period_s)

    clean_temp_files(period_s)


def unzip_product(product, period_s):
    filename = '{}.zip'.format(product['title'])
    zip_path = os.path.join(S2_L1C_PATH, period_s, filename)
    outdir = os.path.join(S2_L1C_PATH, period_s,
                          '{}.SAFE'.format(product['title']))
    if not os.path.exists(outdir):
        print("# Unzip", product['title'])
        unzip(zip_path, delete_zip=False)


def generate_vegetation_indexes(mosaic_name, period_s):
    mosaic_path = os.path.join(settings.IMAGES_PATH, 'mosaic', period_s)
    nir = os.path.join(mosaic_path, '{}_R10m_NIR.vrt'.format(mosaic_name))
    rgb = os.path.join(mosaic_path, '{}_R10m_RGB.vrt'.format(mosaic_name))

    #ndiv
    dst = os.path.join(mosaic_path, '{}_R10m_NDVI.tif'.format(mosaic_name))
    exp = '(im1b1 - im2b1) / (im1b1 + im2b1)'
    run_subprocess(
        '{otb_bin_path}/otbcli_BandMath -il {nir} {rgb} -out {dst} -exp "{exp}"'
        .format(otb_bin_path=settings.OTB_BIN_PATH,
                nir=nir,
                rgb=rgb,
                dst=dst,
                exp=exp))

    #ndwi
    dst = os.path.join(mosaic_path, '{}_R10m_NDWI.tif'.format(mosaic_name))
    exp = '(im1b1 - im2b2) / (im1b1 + im2b2)'
    run_subprocess(
        '{otb_bin_path}/otbcli_BandMath -il {nir} {rgb} -out {dst} -exp "{exp}"'
        .format(otb_bin_path=settings.OTB_BIN_PATH,
                nir=nir,
                rgb=rgb,
                dst=dst,
                exp=exp))

    #evi
    dst = os.path.join(mosaic_path, '{}_R10m_EVI.tif'.format(mosaic_name))
    exp = '(2.5 * ((im1b1 - im2b1) / (im1b1 + 6 * im2b1 - 7.5 * im2b3 + 1)))'
    run_subprocess(
        '{otb_bin_path}/otbcli_BandMath -il {nir} {rgb} -out {dst} -exp "{exp}"'
        .format(otb_bin_path=settings.OTB_BIN_PATH,
                nir=nir,
                rgb=rgb,
                dst=dst,
                exp=exp))

    #savi
    dst = os.path.join(mosaic_path, '{}_R10m_SAVI.tif'.format(mosaic_name))
    exp = '((im1b1 - im2b1) * 1.5 / (im1b1 + im2b1 + 0.5))'
    run_subprocess(
        '{otb_bin_path}/otbcli_BandMath -il {nir} {rgb} -out {dst} -exp "{exp}"'
        .format(otb_bin_path=settings.OTB_BIN_PATH,
                nir=nir,
                rgb=rgb,
                dst=dst,
                exp=exp))


def concatenate_results(mosaic_name, period_s):
    mosaic_path = os.path.join(settings.IMAGES_PATH, 'mosaic', period_s)
    tif_10m = f's2_{period_s}_10m.tif'
    tif_20m = f's2_{period_s}_20m.tif'

    R10m_B02 = os.path.join(mosaic_path, '{}_R10m_B02.tif'.format(mosaic_name))
    R10m_B03 = os.path.join(mosaic_path, '{}_R10m_B03.tif'.format(mosaic_name))
    R10m_B04 = os.path.join(mosaic_path, '{}_R10m_B04.tif'.format(mosaic_name))
    R10m_B08 = os.path.join(mosaic_path, '{}_R10m_B08.tif'.format(mosaic_name))
    R10m_NDVI = os.path.join(mosaic_path,
                             '{}_R10m_NDVI.tif'.format(mosaic_name))
    R10m_NDVI = os.path.join(mosaic_path,
                             '{}_R10m_NDWI.tif'.format(mosaic_name))
    R10m_EVI = os.path.join(mosaic_path, '{}_R10m_EVI.tif'.format(mosaic_name))
    R10m_SAVI = os.path.join(mosaic_path,
                             '{}_R10m_SAVI.tif'.format(mosaic_name))
    src = ' '.join([
        R10m_B02, R10m_B03, R10m_B04, R10m_B08, R10m_NDVI, R10m_NDVI, R10m_EVI,
        R10m_SAVI
    ])
    run_subprocess(
        '{otb_bin_path}/otbcli_ConcatenateImages -il {src} -out {dst}'.format(
            otb_bin_path=settings.OTB_BIN_PATH,
            src=src,
            dst=os.path.join(mosaic_path, tif_10m)))

    R20m_B05 = os.path.join(mosaic_path, '{}_R20m_B05.tif'.format(mosaic_name))
    R20m_B06 = os.path.join(mosaic_path, '{}_R20m_B06.tif'.format(mosaic_name))
    R20m_B07 = os.path.join(mosaic_path, '{}_R20m_B07.tif'.format(mosaic_name))
    R20m_B8A = os.path.join(mosaic_path, '{}_R20m_B8A.tif'.format(mosaic_name))
    R20m_B11 = os.path.join(mosaic_path, '{}_R20m_B11.tif'.format(mosaic_name))
    R20m_B12 = os.path.join(mosaic_path, '{}_R20m_B12.tif'.format(mosaic_name))
    src = ' '.join(
        [R20m_B05, R20m_B06, R20m_B07, R20m_B8A, R20m_B11, R20m_B12])
    run_subprocess(
        '{otb_bin_path}/otbcli_ConcatenateImages -il {src} -out {dst}'.format(
            otb_bin_path=settings.OTB_BIN_PATH,
            src=src,
            dst=os.path.join(mosaic_path, tif_20m)))


def clip_results(period_s):
    mosaic_path = os.path.join(settings.IMAGES_PATH, 'mosaic', period_s)
    tif_10m = f's2_{period_s}_10m.tif'
    tif_20m = f's2_{period_s}_20m.tif'

    srcs = [tif_10m, tif_20m]

    for src in srcs:
        run_subprocess(
            '{gdal_bin_path}/gdalwarp -of GTiff -cutline {aoi} -crop_to_cutline {src} {dst}'
            .format(gdal_bin_path=settings.GDAL_BIN_PATH,
                    aoi=AOI_UTM_PATH,
                    src=os.path.join(mosaic_path, src),
                    dst=os.path.join(RESULTS_PATH, src)))


def get_canonical_names(prods):
    r = [os.path.basename(p) for p in prods]
    r = [n.split('_') for n in r]
    r = ["_".join([ps[i] for i in [0, 2, 4, 5]]) for ps in r]
    return dict(zip(r, prods))


def sen2_preprocess(product_path, period_s):
    cmd = "python3 {}/preprocess.py -v -o {} -res 10 {}".format(
        settings.S2M_CLI_PATH, os.path.join(S2_L2A_PATH, period_s),
        product_path)
    print(cmd)
    os.system(cmd)


def create_rgb_rasters(period):
    period_s = '{dfrom}_{dto}'.format(dfrom=period.date_from.strftime("%Y%m"),
                                      dto=period.date_to.strftime("%Y%m"))

    src_path = os.path.join(RESULTS_PATH, f's2_{period_s}_10m.tif')
    dst_path = os.path.join(RGB_PATH, os.path.basename(src_path))

    if not os.path.exists(dst_path):
        logger.info("Build RGB Sentinel-2 raster")
        write_rgb_raster(src_path=src_path,
                         dst_path=dst_path,
                         bands=(3, 2, 1),
                         in_range=((0, 3000), (0, 3000), (0, 3000)))
    extent = get_raster_extent(dst_path)
    raster, _ = Raster.objects.update_or_create(
        period=period,
        slug="s2",
        defaults=dict(name="Sentinel-2 (RGB, 10m)", extent_geom=extent))
    with open(dst_path, 'rb') as f:
        raster.file.save(f's2.tif', File(f, name='s2.tif'))


def clean_temp_files(period_s):
    for dirname in glob(os.path.join(S2_L1C_PATH, period_s, '*.SAFE')):
        shutil.rmtree(dirname)
    shutil.rmtree(os.path.join(S2_L2A_PATH, period_s))
    shutil.rmtree(os.path.join(settings.IMAGES_PATH, 'mosaic', period_s))
