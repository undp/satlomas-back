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
from lomas_changes.utils import run_subprocess, unzip, write_rgb_raster

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
# "results" directory contains post-processed chips
RESULTS_DIR = os.path.join(DATA_DIR, 'results')

AOI_UTM_PATH = os.path.join(DATA_DIR, 'aoi_utm.gpkg')
EXTENT_PATH = os.path.join(DATA_DIR, 'extent.geojson')
EXTENT_UTM_PATH = os.path.join(DATA_DIR, 'extent_utm.geojson')

MAX_CLOUD_PERC = 20

# extract_chips
BANDS = (1, 2, 3)
NUM_CLASSES = 2
SIZE = 160
STEP_SIZE = 160

# predict
BATCH_SIZE = 64
MODEL_PATH = os.path.join(DATA_DIR, 'lomas_sen2_v10.h5')
BIN_THRESHOLD = 0.4


@job('processing')
def process_period(job):
    date_from = datetime.strptime(job.kwargs['date_from'], '%Y-%m-%d')
    date_to = datetime.strptime(job.kwargs['date_to'], '%Y-%m-%d')

    ### Processing pipeline ###

    proc_scene_dir = download_and_build_composite(date_from, date_to)
    # TODO: Load RGB raster on DB
    # chips_dir = extract_chips_from_scene(proc_scene_dir)
    # predict_chips_dir = predict_scene(chips_dir)
    # result_path = postprocess_scene(predict_chips_dir)

    # logger.info("Result path: %s", result_path)
    # TODO: Load result raster on DB


def download_and_build_composite(date_from, date_to):
    from lomas_changes.utils import clip
    from sentinelsat.sentinel import SentinelAPI, geojson_to_wkt, read_geojson

    period_s = '{dfrom}_{dto}'.format(dfrom=date_from.strftime("%Y%m%d"),
                                      dto=date_to.strftime("%Y%m%d"))

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
        logger.info("Unzip %s", p)
        unzip(p, delete_zip=False)

    # Build mosaic
    proc_scene_dir = os.path.join(PROC_DIR, period_s)

    mosaic_dir = os.path.join(proc_scene_dir, 'mosaic')
    os.makedirs(mosaic_dir, exist_ok=True)
    # FIXME: Read bounds from EXTENT_UTM_PATH
    xmin, ymin, xmax, ymax = [
        260572.3994411753083114, 8620358.0515629947185516,
        324439.4877797830849886, 8720597.2414500378072262
    ]
    cmd = f"python3 {settings.S2M_CLI_PATH}/mosaic.py " \
            f"-te {xmin} {ymin} {xmax} {ymax} " \
            f"-e 32718 -res 10 -v " \
            f"-p {settings.S2M_NUM_JOBS} " \
            f"-o {mosaic_dir} {raw_dir}"
    run_subprocess(cmd)

    import pdb
    pdb.set_trace()

    # Use gdalbuildvrt to concatenate bands

    # tci_path = glob(
    #     os.path.join(raw_scene_dir, 'GRANULE', '*', 'IMG_DATA', 'R10m',
    #                  '*_TCI_*.jp2'))[0]

    # Clip virtual raster to extent and store it on proc dir
    # proc_scene_dir = os.path.join(PROC_DIR, period_s)
    # clipped_tci_path = os.path.join(proc_scene_dir, 'tci.tif')
    # clip(src=tci_path, dst=clipped_tci_path, aoi=EXTENT_UTM_PATH)

    return proc_scene_dir


def extract_chips_from_scene(scene_dir):
    from satlomas.chips import extract_chips

    rasters = glob(os.path.join(scene_dir, '*.tif'))
    logger.info("Num. rasters: %i", len(rasters))

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

    logger.info("Delete chips directory")
    shutil.rmtree(chips_dir)

    return predict_chips_dir


def postprocess_scene(predict_chips_dir):
    from satlomas.unet.postprocess import (clip, coalesce_and_binarize_all,
                                           merge_all)

    result_path = os.path.join(RESULTS_DIR,
                               f'{os.path.basename(predict_chips_dir)}.tif')

    with tempfile.TemporaryDirectory() as tmpdir:
        bin_path = os.path.join(tmpdir, 'bin')
        logger.info(
            "Coalesce and binarize all in %s into %s (with threshold %d)",
            predict_chips_dir, bin_path, BIN_THRESHOLD)
        coalesce_and_binarize_all(input_dir=predict_chips_dir,
                                  output_dir=bin_path,
                                  threshold=BIN_THRESHOLD)

        merged_path = os.path.join(tmpdir, 'merged.tif')
        logger.info("Merge all binarized chips on %s into %s", bin_path,
                    merged_path)
        merge_all(input_dir=bin_path, output=merged_path)

        logger.info("Clip merged raster %s into %s using AOI at %s",
                    merged_path, result_path, AOI_UTM_PATH)
        clip(src=merged_path, dst=result_path, aoi=AOI_UTM_PATH)

    logger.info("Delete predict chips")
    shutil.rmtree(predict_chips_dir)

    return result_path


# def create_rgb_rasters(period):
#     period_s = '{dfrom}_{dto}'.format(dfrom=period.date_from.strftime("%Y%m"),
#                                       dto=period.date_to.strftime("%Y%m"))

#     src_path = os.path.join(RESULTS_PATH, f's2_{period_s}_10m.tif')
#     dst_path = os.path.join(RGB_PATH, os.path.basename(src_path))

#     if not os.path.exists(dst_path):
#         logger.info("Build RGB Sentinel-2 raster")
#         write_rgb_raster(src_path=src_path,
#                          dst_path=dst_path,
#                          bands=(3, 2, 1),
#                          in_range=((0, 3000), (0, 3000), (0, 3000)))
#     raster, _ = Raster.objects.update_or_create(
#         period=period, slug="s2", defaults=dict(name="Sentinel-2 (RGB, 10m)"))
#     with open(dst_path, 'rb') as f:
#         raster.file.save(f's2.tif', File(f, name='s2.tif'))
