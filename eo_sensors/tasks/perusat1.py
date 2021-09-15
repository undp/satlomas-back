import logging
import os
import shutil
import sys
import tempfile
import multiprocessing as mp
from functools import partial
from datetime import datetime
from glob import glob

from django.contrib.gis.gdal import DataSource
from django.contrib.gis.geos import GEOSGeometry
from django.core.files import File
from eo_sensors.clients import SFTPClient
from eo_sensors.models import Raster, Sources
from eo_sensors.tasks import APP_DATA_DIR, TASKS_DATA_DIR
from eo_sensors.utils import unzip, create_raster_tiles, run_command
from jobs.utils import enqueue_job, job

# Configure loggers
out_handler = logging.StreamHandler(sys.stdout)
out_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
out_handler.setLevel(logging.INFO)

logger = logging.getLogger(__name__)
logger.addHandler(out_handler)
logger.setLevel(logging.INFO)

satlomasproc_logger = logging.getLogger("satlomasproc")
satlomasproc_logger.addHandler(out_handler)
satlomasproc_logger.setLevel(level=logging.INFO)

# Base directories
PS1_DATA_DIR = os.path.join(APP_DATA_DIR, "ps1")
PS1_TASKS_DATA_DIR = os.path.join(TASKS_DATA_DIR, "ps1")

# Files needed for tasks
AOI_PATH = os.path.join(PS1_DATA_DIR, "aoi_utm.geojson")
MODEL_PATH = os.path.join(PS1_DATA_DIR, "weights", "lomas_ps1_v6.h5")

# Directories used in the processing pipeline
# "raw" directory contains uncompressed Level-1 PeruSat-1 scenes
RAW_DIR = os.path.join(PS1_TASKS_DATA_DIR, "raw")
# "proc" directory contains pansharpened scenes (result of perusatproc)
PROC_DIR = os.path.join(PS1_TASKS_DATA_DIR, "proc")
# "tci" directory contains the true color image (TCI) RGB rasters
TCI_DIR = os.path.join(PS1_TASKS_DATA_DIR, "tci")
# "chips" dreictory contains all image chips for prediction
CHIPS_DIR = os.path.join(PS1_TASKS_DATA_DIR, "chips")
# "predict" directory contains result chips from prediction
PREDICT_DIR = os.path.join(PS1_TASKS_DATA_DIR, "predict")
# "results" directory contains final classification result as RGB raster
# (using a colormap).
RESULTS_DIR = os.path.join(PS1_TASKS_DATA_DIR, "results")

# Constants
RESCALE_RANGE = ((85, 238), (102, 221), (113, 200))
BANDS = (1, 2, 3)  # RGB
CLASSES = ("C", "D", "N", "U", "V")
SIZE = 320
STEP_SIZE = 160
BATCH_SIZE = 32
BIN_THRESHOLD = 0.4


@job("processing")
def import_scene_from_sftp(job):
    """Connects to an SFTP server and downloads a scene"""

    sftp_conn_info = job.kwargs["sftp_conn_info"]
    filepath = job.kwargs["file"]

    client = SFTPClient(**sftp_conn_info)
    with tempfile.TemporaryDirectory() as tmpdir:
        basename = os.path.basename(filepath)
        id_s = f"{job.pk}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        scene_dir = os.path.join(RAW_DIR, id_s)

        # Download file and extract to RAW_DIR
        dst = os.path.join(tmpdir, basename)
        logger.info("Download %s to %s", filepath, dst)
        client.get(filepath, dst)
        logger.info("Unzip %s into %s", dst, scene_dir)
        unzip(dst, scene_dir)

        enqueue_job(
            "eo_sensors.tasks.perusat1.pansharpen_scene",
            scene_dir=scene_dir,
            queue="processing",
        )


@job("processing")
def pansharpen_scene(job):
    raw_scene_dir = job.kwargs["scene_dir"]

    from perusatproc.console.process import process_product

    basename = os.path.basename(raw_scene_dir)
    proc_scene_dir = os.path.join(PROC_DIR, basename)

    logger.info("Process %s into %s", raw_scene_dir, proc_scene_dir)
    process_product(raw_scene_dir, proc_scene_dir)

    logger.info("Delete raw scene directory")
    shutil.rmtree(raw_scene_dir)

    enqueue_job(
        "eo_sensors.tasks.perusat1.create_tci_rgb_rasters",
        scene_dir=proc_scene_dir,
        queue="processing",
    )


@job("processing")
def create_tci_rgb_rasters(job):
    scene_dir = job.kwargs["scene_dir"]

    rasters = glob(os.path.join(scene_dir, "*.tif"))
    logger.info("Num. rasters: %i", len(rasters))

    basename = os.path.basename(scene_dir)
    tci_scene_dir = os.path.join(TCI_DIR, basename)

    # Extract scene date from basename
    # eg. "052_DS_PER1_201804111527270_PS1_W077S12_016945.vrt"
    #                 |YYYYmmdd|
    logger.info("Basename: %s", basename)
    date_str = basename.split("_")[3][:8]
    scene_date = datetime.strptime(date_str, "%Y%m%d").date()
    logger.info("Scene date: %s", scene_date)

    with mp.Pool(mp.cpu_count()) as pool:
        worker = partial(create_tci_raster_geotiff, tci_scene_dir=tci_scene_dir, scene_date=scene_date)
        tif_paths = pool.map(worker, rasters)

    # Merge TCI tifs into a single raster for uploading and further processing
    merged_path = os.path.join(tci_scene_dir, f'{basename}.tif')
    if not os.path.exists(merged_path):
        run_command(f"gdalwarp -overwrite -multi -wo NUM_THREADS=ALL_CPUS -co TILED=YES -co COMPRESS=DEFLATE -co BIGTIFF=YES {' '.join(tif_paths)} {merged_path}")

    raster = create_tci_raster_object(merged_path, scene_date=scene_date)
    create_raster_tiles(raster, levels=(6, 17), n_jobs=mp.cpu_count())

    enqueue_job(
        "eo_sensors.tasks.perusat1.extract_chips_from_scene",
        scene_dir=tci_scene_dir,
        queue="processing",
    )


def create_tci_raster_geotiff(src_path, *, tci_scene_dir, scene_date):
    from satlomasproc.chips.utils import rescale_intensity, sliding_windows
    import rasterio
    import numpy as np

    # Rescale all images to the same intensity range for true color images
    dst_path = os.path.join(tci_scene_dir, os.path.basename(src_path))
    if os.path.exists(dst_path):
        logger.warn("%s already exists", dst_path)
        return dst_path
    os.makedirs(tci_scene_dir, exist_ok=True)
    with rasterio.open(src_path) as src:
        profile = src.profile.copy()
        profile.update(dtype=np.uint8, count=3, nodata=0, tiled=True)
        try:
            os.remove(dst_path)
        except OSError:
            pass
        with rasterio.open(dst_path, "w", **profile) as dst:
            for _, window in src.block_windows(1):
                img = np.array([src.read(b, window=window) for b in BANDS])
                nodata_mask = (img == src.nodata)
                img = rescale_intensity(
                    img, rescale_mode="values", rescale_range=RESCALE_RANGE
                )
                img[nodata_mask] = 0
                for b in BANDS:
                    dst.write(img[b-1].astype(np.uint8), b, window=window)
    logger.info("%s written", dst_path)
    return dst_path


def create_tci_raster_object(tif_path, *, scene_date):
    # Create Raster object, upload file and generate tiles
    raster, _ = Raster.objects.update_or_create(
        source=Sources.PS1,
        date=scene_date,
        slug=f"tci",
        defaults=dict(name="True-color image (RGB)"),
    )
    with open(tif_path, "rb") as f:
        if raster.file:
            raster.file.delete()
        raster.file.save(f"tci.tif", File(f, name="tci.tif"))
    return raster


@job("processing")
def extract_chips_from_scene(job):
    scene_dir = job.kwargs["scene_dir"]

    from satlomasproc.chips import extract_chips

    rasters = glob(os.path.join(scene_dir, "*.tif"))
    logger.info("Num. rasters: %i", len(rasters))

    chips_dir = os.path.join(CHIPS_DIR, os.path.basename(scene_dir))
    logger.info("Extract chips on images from %s into %s", scene_dir, chips_dir)

    extract_chips(
        rasters,
        aoi=AOI_PATH,
        bands=BANDS,
        type="tif",
        size=SIZE,
        step_size=STEP_SIZE,
        output_dir=chips_dir,
        write_geojson=False,
    )

    enqueue_job(
        "eo_sensors.tasks.perusat1.predict_scene",
        chips_dir=chips_dir,
        queue="processing",
    )


@job("processing")
def predict_scene(job):
    chips_dir = job.kwargs["chips_dir"]

    from satlomasproc.unet.predict import PredictConfig, predict

    predict_chips_dir = os.path.join(PREDICT_DIR, os.path.basename(chips_dir))
    cfg = PredictConfig(
        images_path=chips_dir,
        results_path=predict_chips_dir,
        batch_size=BATCH_SIZE,
        model_path=MODEL_PATH,
        height=SIZE,
        width=SIZE,
        n_channels=len(BANDS),
        n_classes=len(CLASSES),
    )
    logger.info("Predict chips on %s", predict_chips_dir)
    predict(cfg)

    logger.info("Delete chips directory")
    shutil.rmtree(chips_dir)

    enqueue_job(
        "eo_sensors.tasks.perusat1.postprocess_scene",
        predict_chips_dir=predict_chips_dir,
        queue="processing",
    )


@job("processing")
def postprocess_scene(job):
    predict_chips_dir = job.kwargs["predict_chips_dir"]

    from satlomasproc.unet.postprocess import (
        clip,
        coalesce_and_binarize_all,
        merge_all,
        smooth_stitch,
    )

    result_path = os.path.join(
        RESULTS_DIR, f"{os.path.basename(predict_chips_dir)}.tif"
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        bin_path = os.path.join(tmpdir, "bin")
        smooth_path = os.path.join(tmpdir, "smooth")

        logger.info("Smooth stitch all in %s into %s")
        smooth_stitch(bin_path, smooth_path)

        logger.info(
            "Coalesce and binarize all in %s into %s (with threshold %d)",
            predict_chips_dir,
            smooth_path,
            BIN_THRESHOLD,
        )
        coalesce_and_binarize_all(
            input_dir=predict_chips_dir, output_dir=bin_path, threshold=BIN_THRESHOLD
        )

        merged_path = os.path.join(tmpdir, "merged.tif")
        logger.info("Merge all binarized chips on %s into %s", bin_path, merged_path)
        merge_all(input_dir=bin_path, output=merged_path)

        logger.info(
            "Clip merged raster %s into %s using AOI at %s",
            merged_path,
            result_path,
            AOI_PATH,
        )
        clip(src=merged_path, dst=result_path, aoi=AOI_PATH)

    logger.info("Delete predict chips")
    shutil.rmtree(predict_chips_dir)


def load_data(period, product_id):
    # create_rgb_rasters(period, product_id)
    load_raster(period, product_id)
    load_mask_and_objects(period, product_id)


def load_raster(period, product_id):
    logger.info(f"Load {product_id} raster")
    Raster.objects.update_or_create(
        period=period, slug="ps1", defaults=dict(name=product_id)
    )


def load_mask_and_objects(period, product_id):
    import geopandas as gpd
    import shapely.wkt
    from shapely.ops import unary_union

    logging.info("Reproject to epsg:4326")
    src_path = os.path.join(RESULTS_DIR, product_id, "objects.geojson")
    dst_path = os.path.join(RESULTS_DIR, product_id, "objects_4326.geojson")
    data = gpd.read_file(src_path)
    data_proj = data.copy()
    data_proj["geometry"] = data_proj["geometry"].to_crs(epsg=4326)
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
        mask_type="roofs",
        defaults=dict(geom=GEOSGeometry(multipoly.wkt)),
    )

    Object.objects.filter(period=period).delete()
    for poly in polys:
        Object.objects.create(
            period=period, object_type="roof", geom=GEOSGeometry(poly.wkt)
        )
