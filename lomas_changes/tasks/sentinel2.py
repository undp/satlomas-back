import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from glob import glob

import lomas_changes
from django.conf import settings
from django.core.files import File
from jobs.utils import enqueue_job, job
from lomas_changes.models import Raster
from lomas_changes.utils import run_subprocess, write_paletted_rgb_raster, create_raster

# Configure logger
logger = logging.getLogger(__name__)
out_handler = logging.StreamHandler(sys.stdout)
out_handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
out_handler.setLevel(logging.INFO)
logger.addHandler(out_handler)
logger.setLevel(logging.INFO)

# Base directory
DATA_DIR = os.path.join(settings.DATA_DIR, 'lomas_changes', 's2')
# "raw" directory contains uncompressed Sentinel-2 products
RAW_DIR = os.path.join(DATA_DIR, 'raw')
# "proc" directory contains already scaled TCI images
PROC_DIR = os.path.join(DATA_DIR, 'proc')
# "chips" dreictory contains all image chips for prediction
CHIPS_DIR = os.path.join(DATA_DIR, 'chips')
# "predict" directory contains result chips from prediction
PREDICT_DIR = os.path.join(DATA_DIR, 'predict')
# "results" directory contains final rasters.  In this case: 1) Sentinel-2 RGB
# raster and 2) Classification result as RGB raster (using a colormap)
RESULTS_DIR = os.path.join(DATA_DIR, 'results')

#MASK_DIR = os.path.join(DATA_DIR, 'mask')
RESULTS_RGB_DIR = os.path.join(RESULTS_DIR, 'rgb')

AOI_UTM_PATH = os.path.join(DATA_DIR, 'aoi_utm.gpkg')
EXTENT_PATH = os.path.join(DATA_DIR, 'extent.geojson')
EXTENT_UTM_PATH = os.path.join(DATA_DIR, 'extent_utm.geojson')

MAX_CLOUD_PERC = 50

# extract_chips
BANDS = (1, 2, 3)
NUM_CLASSES = 2
SIZE = 160
STEP_SIZE = 80

# predict
BATCH_SIZE = 64
MODEL_PATH = os.path.join(DATA_DIR, 'lomas_sen2_v10.h5')
BIN_THRESHOLD = 0.2

COLORMAP = ['ff0000', '00c8ff']


@job('processing')
def process_period(job):
    date_from = datetime.strptime(job.kwargs['date_from'], '%Y-%m-%d')
    date_to = datetime.strptime(job.kwargs['date_to'], '%Y-%m-%d')

    ### Processing pipeline ###

    tci_path = download_and_build_composite(date_from, date_to)
    create_raster(tci_path,
                  slug='s2-rgb',
                  date=date_to,
                  name='Sentinel-2 (RGB, 10m)')

    chips_dir = extract_chips_from_scene([tci_path])
    predict_chips_dir = predict_scene(chips_dir)
    result_path = postprocess_scene(predict_chips_dir)
    create_loss_raster(result_path, date=date_to)


def download_and_build_composite(date_from, date_to):
    from lomas_changes.utils import clip, rescale_byte, unzip
    from sentinelsat.sentinel import SentinelAPI, geojson_to_wkt, read_geojson

    period_s = '{dfrom}_{dto}'.format(dfrom=date_from.strftime("%Y%m%d"),
                                      dto=date_to.strftime("%Y%m%d"))
    proc_scene_dir = os.path.join(PROC_DIR, period_s)
    tci_path = os.path.join(proc_scene_dir, 'tci.tif')

    if os.path.exists(tci_path):
        logger.info("TCI file already generated at %s", tci_path)
        return tci_path

    if not settings.SCIHUB_USER or not settings.SCIHUB_PASS:
        raise "SCIHUB_USER and/or SCIHUB_PASS are not set. " + \
              "Please read the Configuration section on README."

    api = SentinelAPI(settings.SCIHUB_USER, settings.SCIHUB_PASS,
                      settings.SCIHUB_URL)

    extent = read_geojson(EXTENT_PATH)
    footprint = geojson_to_wkt(extent)
    logger.info(
        "Query S2MSI2A products with up to %d%% cloud cover from %s to %s",
        MAX_CLOUD_PERC, date_from, date_to)
    products = api.query(footprint,
                         date=(date_from, date_to),
                         platformname='Sentinel-2',
                         cloudcoverpercentage=(0, MAX_CLOUD_PERC),
                         producttype='S2MSI2A')
    logger.info("Found %d products", len(products))

    raw_dir = os.path.join(RAW_DIR, period_s)
    os.makedirs(raw_dir, exist_ok=True)

    # Filter already downloaded products
    products_to_download = {
        k: v
        for k, v in products.items()
        if not (os.path.exists(
            os.path.join(raw_dir, '{}.zip'.format(v['title']))) or os.path.
                exists(os.path.join(raw_dir, '{}.SAFE'.format(v['title']))))
    }

    # Download products
    if products_to_download:
        logger.info("Download all products (%d)", len(products_to_download))
        api.download_all(products_to_download, directory_path=raw_dir)

    # Unzip compressed files, if there are any
    for p in glob(os.path.join(raw_dir, '*.zip')):
        name, _ = os.path.splitext(os.path.basename(p))
        p_dir = os.path.join(raw_dir, f'{name}.SAFE')
        if not os.path.exists(p_dir):
            logger.info("Unzip %s", p)
            unzip(p, delete_zip=False)

    # Build mosaic
    mosaic_dir = os.path.join(proc_scene_dir, 'mosaic')
    os.makedirs(mosaic_dir, exist_ok=True)
    # FIXME: Read bounds from EXTENT_UTM_PATH
    xmin, ymin, xmax, ymax = [
        261215.0000000000000000, 8620583.0000000000000000,
        323691.8790999995544553, 8719912.0846999995410442
    ]
    cmd = f"python3 {settings.S2M_CLI_PATH}/mosaic.py " \
            f"-te {xmin} {ymin} {xmax} {ymax} " \
            f"-e 32718 -res 10 -v " \
            f"-p {settings.S2M_NUM_JOBS} " \
            f"-o {mosaic_dir} {raw_dir}"
    run_subprocess(cmd)

    # Get mosaic band rasters
    mosaic_rgb_paths = [
        glob(os.path.join(mosaic_dir, f'*_{band}.tif'))
        for band in ['B04', 'B03', 'B02']
    ]
    mosaic_rgb_paths = [p[0] for p in mosaic_rgb_paths if p]
    logger.info("RGB paths: %s", mosaic_rgb_paths)

    # Use gdalbuildvrt to concatenate RGB bands from mosaic
    vrt_path = os.path.join(mosaic_dir, 'tci.vrt')
    cmd = f"gdalbuildvrt -separate {vrt_path} {' '.join(mosaic_rgb_paths)}"
    run_subprocess(cmd)

    # Clip to extent and rescale virtual raster
    clipped_tci_path = os.path.join(mosaic_dir, 'tci.tif')
    clip(src=vrt_path, dst=clipped_tci_path, aoi=EXTENT_UTM_PATH)

    # Rescale image
    rescale_byte(src=clipped_tci_path, dst=tci_path, in_range=(100, 3000))

    return tci_path


def extract_chips_from_scene(rasters):
    from satlomas.chips import extract_chips

    logger.info("Num. rasters to extract chips: %i", len(rasters))

    scene_dir = os.path.dirname(rasters[0])
    chips_dir = os.path.join(CHIPS_DIR, os.path.basename(scene_dir))
    logger.info("Extract chips on images from %s into %s", scene_dir,
                chips_dir)

    extract_chips(rasters,
                  aoi=AOI_UTM_PATH,
                  bands=BANDS,
                  type='tif',
                  size=SIZE,
                  step_size=STEP_SIZE,
                  output_dir=chips_dir)

    return chips_dir


def predict_scene(chips_dir):
    from satlomas.unet.predict import PredictConfig, predict

    predict_chips_dir = os.path.join(PREDICT_DIR, os.path.basename(chips_dir))
    cfg = PredictConfig(images_path=chips_dir,
                        results_path=predict_chips_dir,
                        batch_size=BATCH_SIZE,
                        model_path=MODEL_PATH,
                        height=SIZE,
                        width=SIZE,
                        n_channels=len(BANDS),
                        n_classes=NUM_CLASSES)
    logger.info("Predict chips on %s", predict_chips_dir)
    predict(cfg)

    # logger.info("Delete chips directory")
    # shutil.rmtree(chips_dir)

    return predict_chips_dir


def postprocess_scene(predict_chips_dir):
    from lomas_changes.utils import clip
    from satlomas.unet.postprocess import (coalesce_and_binarize_all,
                                           merge_all, smooth_stitch)

    result_path = os.path.join(RESULTS_DIR,
                               f'{os.path.basename(predict_chips_dir)}.tif')

    with tempfile.TemporaryDirectory() as tmpdir:
        smooth_dir = os.path.join(tmpdir, 'smooth')
        logger.info("Stitch prediction chips at %s on %s", predict_chips_dir,
                    smooth_dir)
        smooth_stitch(input_dir=predict_chips_dir, output_dir=smooth_dir)

        bin_path = os.path.join(tmpdir, 'bin')
        logger.info(
            "Coalesce and binarize all in %s into %s (with threshold %f)",
            predict_chips_dir, bin_path, BIN_THRESHOLD)
        coalesce_and_binarize_all(input_dir=smooth_dir,
                                  output_dir=bin_path,
                                  threshold=BIN_THRESHOLD)

        merged_path = os.path.join(tmpdir, 'merged.tif')
        logger.info("Merge all binarized chips on %s into %s", bin_path,
                    merged_path)
        merge_all(input_dir=bin_path, output=merged_path)

        clipped_path = os.path.join(tmpdir, 'clipped.tif')
        logger.info("Clip merged raster %s into %s using AOI at %s",
                    merged_path, clipped_path, AOI_UTM_PATH)
        clip(src=merged_path, dst=clipped_path, aoi=AOI_UTM_PATH)

    # logger.info("Delete predict chips")
    # shutil.rmtree(predict_chips_dir)

    return clipped_path


def create_loss_raster(result_path, *, date):
    with tempfile.TemporaryDirectory() as tmpdir:
        loss_rgb_path = os.path.join(tmpdir, 's2-loss-rgb.tif')
        logger.info("Write paletted RGB raster %s into %s", result_path,
                    loss_rgb_path)
        write_paletted_rgb_raster(result_path,
                                  loss_rgb_path,
                                  colormap=COLORMAP)
        create_raster(loss_rgb_path,
                      slug='s2-loss',
                      date=date,
                      name='Sentinel-2 Loss Mask')
