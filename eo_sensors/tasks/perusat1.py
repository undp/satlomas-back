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
from eo_sensors.utils import unzip, create_raster_tiles, run_command, write_rgb_raster, hex_to_dec_string
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
# "postprocess" directory contains the different steps of post-processing
#POSTPROCESS_DIR = os.path.join("/tmp", "eo-sensors-data", "postprocess")
POSTPROCESS_DIR = os.path.join(PS1_TASKS_DATA_DIR, "postprocess")
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
BIN_THRESHOLD = 0.2
CMAP = ["c70039", "eddd53", None, "2a7b9b", "33a02c"]


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
    from satlomasproc.chips.utils import calculate_raster_percentiles

    scene_dir = job.kwargs["scene_dir"]

    rasters = glob(os.path.join(scene_dir, "*.tif"))
    logger.info("Num. rasters: %i", len(rasters))

    basename = os.path.basename(scene_dir)
    tci_scene_dir = os.path.join(TCI_DIR, basename)

    scene_date = _extract_from_ps1_id(basename)

    # Create virtual raster
    vrt_path = os.path.join(tci_scene_dir, "tci.vrt")
    logger.info("Generate virtual raster from TCI tiles into %s", vrt_path)
    cmd = f"gdalbuildvrt {vrt_path} {' '.join(rasters)}"
    run_command(cmd)
    logger.info("%s written", vrt_path)

    logger.info("Calculate raster percentiles (2, 98) from %s", vrt_path)
    rescale_range = calculate_raster_percentiles(vrt_path, lower_cut=2, upper_cut=98)

    logger.info("Rescale intensities of all TCI tiles")
    with mp.Pool(mp.cpu_count()) as pool:
        worker = partial(create_tci_raster_geotiff, tci_scene_dir=tci_scene_dir, rescale_range=rescale_range)
        tif_paths = pool.map(worker, rasters)

    # Merge TCI tifs into a single raster for uploading and further processing
    logger.info("Merge all rescaled tiles into a single JPEG compressed GeoTIFF")
    merged_path = os.path.join(tci_scene_dir, f'{basename}.tif')
    if not os.path.exists(merged_path):
        run_command(f"gdalwarp -overwrite -multi -wo NUM_THREADS=ALL_CPUS -co TILED=YES -co COMPRESS=JPEG -co PHOTOMETRIC=YCBCR -co BIGTIFF=YES {' '.join(tif_paths)} {merged_path}")
        logger.info("Add internval overviews to %s", merged_path)
        run_command(f"gdaladdo --config COMPRESS_OVERVIEW JPEG --config PHOTOMETRIC_OVERVIEW YCBCR --config INTERLEAVE_OVERVIEW PIXEL {merged_path} 2 4 8 16")

    raster = create_tci_raster_object(merged_path, scene_date=scene_date)
    create_raster_tiles(raster, levels=(6, 17), n_jobs=mp.cpu_count())

    enqueue_job(
        "eo_sensors.tasks.perusat1.extract_chips_from_scene",
        scene_dir=tci_scene_dir,
        queue="processing",
    )


def create_tci_raster_geotiff(src_path, *, tci_scene_dir, rescale_range):
    from satlomasproc.chips.utils import rescale_intensity, sliding_windows
    import rasterio
    import numpy as np

    # Rescale all images to the same intensity range for true color images

    dst_path = os.path.join(tci_scene_dir, os.path.basename(src_path))
    if os.path.exists(dst_path):
        logger.warn("%s already exists", dst_path)
        return dst_path

    logger.info("Rescale image %s into %s", src_path, dst_path)
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
                    img, rescale_mode="values", rescale_range=rescale_range
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

    from eo_sensors.utils import clip
    from satlomasproc.unet.postprocess import (
        smooth_stitch,
        coalesce_and_binarize_all,
        remove_negative_class_all,
        merge_all,
    )

    basename = os.path.basename(predict_chips_dir)

    postprocess_dir = os.path.join(POSTPROCESS_DIR, basename)

    ##smooth_path = os.path.join(postprocess_dir, "smooth")
    #smooth_path = predict_chips_dir
    ##logger.info("Smooth stitch all chips in %s into %s", predict_chips_dir, smooth_path)
    ##smooth_stitch(input_dir=predict_chips_dir, output_dir=smooth_path)

    bin_path = os.path.join(postprocess_dir, "bin")
    logger.info(
        "Coalesce and binarize all in %s into %s (with threshold %f)",
        predict_chips_dir,
        bin_path,
        BIN_THRESHOLD,
    )
    coalesce_and_binarize_all(
        input_dir=predict_chips_dir, output_dir=bin_path, threshold=BIN_THRESHOLD
    )

    neg_path = os.path.join(postprocess_dir, "neg")
    neg_class_num = CLASSES.index("N") + 1
    logger.info(
        "Remove negative class (value = %d) from results from %s into %s",
        neg_class_num, bin_path, neg_path
    )
    remove_negative_class_all(
        input_dir=bin_path, output_dir=neg_path, num_class=neg_class_num
    )

    merged_path = os.path.join(postprocess_dir, "merged.tif")
    logger.info("Merge all binarized chips on %s into %s", neg_path, merged_path)
    merge_all(input_dir=neg_path, output=merged_path)

    results_path = os.path.join(RESULTS_DIR, basename, "mask.tif")
    logger.info(
        "Clip merged raster %s into %s using AOI at %s",
        merged_path,
        results_path,
        AOI_PATH,
    )
    clip(src=merged_path, dst=results_path, aoi=AOI_PATH)

    # TODO: Uncomment after testing
    #logger.info("Delete predict chips")
    #shutil.rmtree(predict_chips_dir)
    #shutil.rmtree(postprocess_dir)

    # TODO: Uncomment after testing
    #enqueue_job(
    #    "eo_sensors.tasks.perusat1.load_results",
    #    results_path=results_path,
    #    queue="processing",
    #)


@job("processing")
def load_results(job):
    results_path = job.kwargs["results_path"]

    name = os.path.basename(os.path.dirname(results_path))
    scene_date = _extract_from_ps1_id(name)

    create_rgb_mask_raster(results_path, scene_date)
    create_masks(results_path, scene_date)
    generate_measurements(scene_date)
    #clean_temp_files()


def create_rgb_mask_raster(mask_path, scene_date):
    rgb_mask_path = os.path.join(os.path.dirname(mask_path), "rgb_mask.tif")
    logger.info("Create RGB land use mask raster")
    write_use_mask_rgb_raster(src_path=mask_path, dst_path=rgb_mask_path)
    raster, _ = Raster.objects.update_or_create(
        source=Sources.PS1,
        date=scene_date,
        slug="mask",
        defaults=dict(name="Land use mask"),
    )
    with open(dst_path, "rb") as f:
        if raster.file:
            raster.file.delete()
        raster.file.save(f"mask.tif", File(f))
    create_raster_tiles(raster, levels=(6, 17), n_jobs=mp.cpu_count())


@write_rgb_raster
def write_use_mask_rgb_raster(img):
    new_img = np.zeros((img.shape[0], img.shape[1], 3), dtype=np.uint8)
    for i in range(len(CMAP)):
        if colormap[i]:
            new_img[img == i + 1] = hex_to_dec_string(colormap[i])
    return new_img


def create_masks(mask_path, scene_date):
    logger.info("Polygonize mask")
    mask_geojson_path = os.path.join(os.path.dirname(mask_path), "mask.geojson")
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

    logger.info("Load land use mask to DB")
    create_use_masks(dst_path, scene_date)


def create_use_masks(geojson_path, scene_date):
    pass
    # TODO: Use Geopandas to read geojson and partition all polygons into class
    # buckets
    #ds = DataSource(geojson_path)
    #for x in range(0, len(ds[0]) - 1):
    #    geom = shapely.wkt.loads(ds[0][x].geom.wkt)
    #    if str(ds[0][x]["DN"]) == "1":
    #        vegetation_polys.append(geom)
    #    elif str(ds[0][x]["DN"]) == "2":
    #        clouds_polys.append(geom)
    #    else:
    #        pass
#
    # TODO: Join all polygons on each class
    #vegetation_mp = unary_union(vegetation_polys)
    #clouds_mp = unary_union(clouds_polys)

    raster = Raster.objects.get(
        source=Sources.PS1, date=scene_date, slug="mask"
    )
    # TODO: For each class
    #CoverageMask.objects.update_or_create(
    #    date=date,
    #    source=Sources.PS1,
    #    kind="V",
    #    defaults=dict(geom=GEOSGeometry(vegetation_mp.wkt), raster=raster),
    #)


def generate_measurements(date):
    logger.info("Generate measurements for each scope")

    for scope in Scope.objects.all():
        for kind in CLASSES:
            if kind == "N":
                continue

            mask = CoverageMask.objects.filter(
                date=date,
                source=Sources.PS1,
                kind=kind,
            ).first()

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
                    date=date,
                    kind=kind,
                    source=Sources.MODIS_VI,
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


def _extract_from_ps1_id(basename):
    """Extract scene date from basename"""
    # eg. "052_DS_PER1_201804111527270_PS1_W077S12_016945.vrt"
    #                 |YYYYmmdd|
    date_str = basename.split("_")[3][:8]
    scene_date = datetime.strptime(date_str, "%Y%m%d").date()
    logger.info("Scene date: %s (basename: %s)", scene_date, basename)
    return scene_date

##
# DEPRECATED
#

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
