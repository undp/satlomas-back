import calendar
import fnmatch
import logging
import os
import shutil
import subprocess
import sys
import time
from glob import glob

import django_rq
import geopandas as gpd
import numpy as np
import pyproj
import rasterio
import requests
import shapely.wkt
from django.conf import settings
from django.contrib.gis.gdal import DataSource
from django.contrib.gis.geos import GEOSGeometry
from django.core.files import File
from django.db import connection
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from shapely.ops import unary_union

import vi_lomas_changes
from scopes.models import Scope
from vi_lomas_changes.models import CoverageMeasurement, Mask, Raster

try:
    import urllib.request as urllib2
except ImportError:
    import urllib2

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Configure logger
logger = logging.getLogger(__name__)
out_handler = logging.StreamHandler(sys.stdout)
out_handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
out_handler.setLevel(logging.INFO)
logger.addHandler(out_handler)
logger.setLevel(logging.INFO)

HEADERS = {'User-Agent': 'get_modis Python 3'}
CHUNKS = 65536

MODIS_PLATFORM = 'MOLA'
MODIS_PRODUCT = 'MYD13Q1.006'
H_PERU = '10'
V_PERU = '10'

LOMAS_MIN = 200
LOMAS_MAX = 1800
FACTOR_ESCALA = 0.0001
UMBRAL_NDVI = 0.2
THRESHOLD = UMBRAL_NDVI / FACTOR_ESCALA

APPDIR = os.path.dirname(vi_lomas_changes.__file__)
EXTENT_PATH = os.path.join(APPDIR, 'data', 'extent.geojson')
SRTM_DEM_PATH = os.path.join(APPDIR, 'data', 'srtm_dem.tif')

VI_ROOT = os.path.join(settings.BASE_DIR, 'data', 'vi')
VI_RAW_DIR = os.path.join(VI_ROOT, 'raw')
VI_TIF_DIR = os.path.join(VI_ROOT, 'tif')
VI_CLIP_DIR = os.path.join(VI_ROOT, 'clip')
VI_MASK_DIR = os.path.join(VI_ROOT, 'masks')
VI_RGB_DIR = os.path.join(VI_ROOT, 'rgb')


def process_all(period):
    download_and_process(period)
    create_rgb_rasters(period)
    create_masks(period)
    generate_measurements(period)


def download_and_process(period):
    date_from, date_to = period.date_from, period.date_to

    year = date_to.year
    doy_begin = date_from.timetuple().tm_yday
    doy_end = date_to.timetuple().tm_yday

    os.makedirs(VI_RAW_DIR, exist_ok=True)
    os.makedirs(VI_TIF_DIR, exist_ok=True)

    logger.info("Download MODIS hdf files")
    tile = 'h{}v{}'.format(H_PERU, V_PERU)
    get_modisfiles(settings.MODIS_USER,
                   settings.MODIS_PASS,
                   MODIS_PLATFORM,
                   MODIS_PRODUCT,
                   year,
                   tile,
                   proxy=None,
                   doy_start=doy_begin,
                   doy_end=doy_end,
                   out_dir=VI_RAW_DIR,
                   verbose=True,
                   ruff=False,
                   get_xml=False)

    extract_subdatasets_as_gtiffs(VI_RAW_DIR, VI_TIF_DIR)

    logger.info("Clip SRTM to extent")
    srtm_clipped_path = os.path.join(VI_ROOT, 'srtm_dem_clipped.tif')
    if not os.path.exists(srtm_clipped_path):
        run_command(
            '{gdal_bin_path}/gdalwarp -of GTiff -cutline {aoi} -crop_to_cutline {src} {dst}'
            .format(gdal_bin_path=settings.GDAL_BIN_PATH,
                    aoi=EXTENT_PATH,
                    src=SRTM_DEM_PATH,
                    dst=srtm_clipped_path))

    logger.info("Calculate SRTM mask")
    with rasterio.open(srtm_clipped_path) as srtm_src:
        srtm = srtm_src.read(1)
        lomas_mask = ((srtm >= LOMAS_MIN) & (srtm <= LOMAS_MAX))

    logger.info("Clip NDVI to extent")
    os.makedirs(VI_CLIP_DIR, exist_ok=True)
    ndvi_path = glob(os.path.join(VI_TIF_DIR, '*h10v10*.hdf_ndvi.tif'))[0]
    ndvi_clipped_path = os.path.join(VI_CLIP_DIR, os.path.basename(ndvi_path))
    if os.path.exists(ndvi_clipped_path):
        os.unlink(ndvi_clipped_path)
    run_command(
        '{gdal_bin_path}/gdalwarp -of GTiff -cutline {extent} -crop_to_cutline {src} {dst}'
        .format(gdal_bin_path=settings.GDAL_BIN_PATH,
                extent=EXTENT_PATH,
                src=ndvi_path,
                dst=ndvi_clipped_path))

    logger.info("Superimpose clipped SRTM and NDVI rasters to align them")
    run_command(
        '{otb_bin_path}/otbcli_Superimpose -inr {inr} -inm {inm} -out {out}'.
        format(otb_bin_path=settings.OTB_BIN_PATH,
               inr=srtm_clipped_path,
               inm=ndvi_clipped_path,
               out=ndvi_clipped_path))

    with rasterio.open(ndvi_clipped_path) as src:
        modis_ndvi = src.read(1)
        modis_meta = src.profile.copy()

    modis_meta['nodata'] = 0
    modis_meta['dtype'] = np.uint8

    logger.info("Build final vegetation mask")
    vegetacion_mask = (modis_ndvi > THRESHOLD)
    verde_mask = (vegetacion_mask & lomas_mask)
    verde = np.copy(modis_ndvi)
    verde[~verde_mask] = 0

    logger.info("Build scaled NDVI mask")
    verde_rango = np.copy(verde)
    verde_rango[(verde >= (0.2 / FACTOR_ESCALA))
                & (verde < (0.4 / FACTOR_ESCALA))] = 1
    verde_rango[(verde >= (0.4 / FACTOR_ESCALA))
                & (verde < (0.6 / FACTOR_ESCALA))] = 2
    verde_rango[(verde >= (0.6 / FACTOR_ESCALA))
                & (verde < (0.8 / FACTOR_ESCALA))] = 3
    verde_rango[verde >= (0.8 / FACTOR_ESCALA)] = 4
    verde_rango[verde < 0] = 0
    verde_rango = verde_rango.astype(dtype=np.uint8)

    verde[verde_mask] = 1
    verde = verde.astype(dtype=np.uint8)

    period_s = f'{date_from.strftime("%Y%m")}-{date_to.strftime("%Y%m")}'

    logger.info("Write vegetation mask")
    os.makedirs(VI_MASK_DIR, exist_ok=True)
    dst_name = os.path.join(VI_MASK_DIR,
                            '{}_vegetation_mask.tif'.format(period_s))
    with rasterio.open(dst_name, 'w', **modis_meta) as dst:
        dst.write(verde, 1)

    # Cloud mask
    logger.info("Clip pixel reliability raster to extent")
    pixelrel_path = glob(os.path.join(VI_TIF_DIR,
                                      '*h10v10*.hdf_pixelrel.tif'))[0]
    pixelrel_clipped_path = os.path.join(VI_CLIP_DIR,
                                         os.path.basename(pixelrel_path))
    if os.path.exists(pixelrel_clipped_path):
        os.unlink(pixelrel_clipped_path)
    run_command(
        '{gdal_bin_path}/gdalwarp -of GTiff -cutline {extent} -crop_to_cutline {src} {dst}'
        .format(gdal_bin_path=settings.GDAL_BIN_PATH,
                extent=EXTENT_PATH,
                src=pixelrel_path,
                dst=pixelrel_clipped_path))

    logger.info("Superimpose pixel rel raster to SRTM raster")
    run_command(
        '{otb_bin_path}/otbcli_Superimpose -inr {inr} -inm {inm} -out {out}'.
        format(otb_bin_path=settings.OTB_BIN_PATH,
               inr=srtm_clipped_path,
               inm=pixelrel_clipped_path,
               out=pixelrel_clipped_path))

    logger.info("Build cloud mask from pixel reliability raster")
    with rasterio.open(pixelrel_clipped_path) as cloud_src:
        clouds = cloud_src.read(1)

    # In clouds 2 is snow/ice and 3 are clouds, and -1 is not processed data
    cloud_mask = np.copy(clouds)
    cloud_mask[(clouds == 2) | (clouds == 3) | (clouds == -1)] = 1
    cloud_mask[(clouds != 2) & (clouds != 3)] = 0
    cloud_mask = cloud_mask.astype(np.uint8)

    dst_name = os.path.join(VI_MASK_DIR, '{}_cloud_mask.tif'.format(period_s))
    with rasterio.open(dst_name, 'w', **modis_meta) as dst:
        dst.write(cloud_mask, 1)

    dst_name = os.path.join(VI_MASK_DIR,
                            '{}_vegetation_range.tif'.format(period_s))
    with rasterio.open(dst_name, 'w', **modis_meta) as dst:
        dst.write(verde_rango, 1)

    # FIXME Write this mask as a temporary file
    logger.info("Create a mask with data from vegetation and clouds")
    verde[cloud_mask == 1] = 2
    dst_name = os.path.join(VI_MASK_DIR,
                            '{}_vegetation_cloud_mask.tif'.format(period_s))
    with rasterio.open(dst_name, 'w', **modis_meta) as dst:
        dst.write(verde, 1)

    clean_temp_files()


def create_rgb_rasters(period):
    period_s = '{dfrom}-{dto}'.format(dfrom=period.date_from.strftime("%Y%m"),
                                      dto=period.date_to.strftime("%Y%m"))

    src_path = os.path.join(VI_MASK_DIR, f'{period_s}_vegetation_range.tif')
    dst_path = os.path.join(VI_RGB_DIR, f'{period_s}_vegetation_range.tif')
    logger.info("Build RGB vegetation raster")
    write_vegetation_range_rgb_raster(src_path=src_path, dst_path=dst_path)
    raster, _ = Raster.objects.update_or_create(period=period,
                                                slug="ndvi",
                                                defaults=dict(name="NDVI"))
    with open(dst_path, 'rb') as f:
        raster.file.save(f'ndvi.tif', File(f, name='ndvi.tif'))

    src_path = os.path.join(VI_MASK_DIR, f'{period_s}_vegetation_mask.tif')
    dst_path = os.path.join(VI_RGB_DIR, f'{period_s}_vegetation_mask.tif')
    logger.info("Build RGB vegetation mask raster")
    write_vegetation_mask_rgb_raster(src_path=src_path, dst_path=dst_path)
    raster, _ = Raster.objects.update_or_create(
        period=period,
        slug="vegetation",
        defaults=dict(name="Vegetation mask"))
    with open(dst_path, 'rb') as f:
        raster.file.save(f'vegetation.tif', File(f))

    src_path = os.path.join(VI_MASK_DIR, f'{period_s}_cloud_mask.tif')
    dst_path = os.path.join(VI_RGB_DIR, f'{period_s}_cloud_mask.tif')
    logger.info("Build RGB cloud mask raster")
    write_cloud_mask_rgb_raster(src_path=src_path, dst_path=dst_path)
    raster, _ = Raster.objects.update_or_create(
        period=period, slug="cloud", defaults=dict(name="Cloud mask"))
    with open(dst_path, 'rb') as f:
        raster.file.save(f'cloud.tif', File(f))


def write_rgb_raster(func):
    def wrapper(*, src_path, dst_path):
        with rasterio.open(src_path) as src:
            img = src.read(1)
            profile = src.profile.copy()
        new_img = func(img)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        profile.update(count=3, dtype=np.uint8)
        with rasterio.open(dst_path, 'w', **profile) as dst:
            for i in range(new_img.shape[2]):
                dst.write(new_img[:, :, i], i + 1)

    return wrapper


def hex_to_dec_string(value):
    return np.array([int(value[i:j], 16) for i, j in [(0, 2), (2, 4), (4, 6)]],
                    np.uint8)


@write_rgb_raster
def write_vegetation_range_rgb_raster(img):
    colormap = ['440154', '31688e', '35b779', 'fde725']
    new_img = np.zeros((img.shape[0], img.shape[1], 3), dtype=np.uint8)
    for i in range(len(colormap)):
        new_img[img == i + 1] = hex_to_dec_string(colormap[i])
    return new_img


@write_rgb_raster
def write_cloud_mask_rgb_raster(img):
    colormap = ['30a7ff']
    new_img = np.zeros((img.shape[0], img.shape[1], 3), dtype=np.uint8)
    for i in range(len(colormap)):
        new_img[img == i + 1] = hex_to_dec_string(colormap[i])
    return new_img


@write_rgb_raster
def write_vegetation_mask_rgb_raster(img):
    colormap = ['149c00']
    new_img = np.zeros((img.shape[0], img.shape[1], 3), dtype=np.uint8)
    for i in range(len(colormap)):
        new_img[img == i + 1] = hex_to_dec_string(colormap[i])
    return new_img


def create_masks(period):
    period_s = '{dfrom}-{dto}'.format(dfrom=period.date_from.strftime("%Y%m"),
                                      dto=period.date_to.strftime("%Y%m"))

    logger.info("Polygonize mask")
    src_path = os.path.join(VI_MASK_DIR,
                            '{}_vegetation_cloud_mask.tif'.format(period_s))
    dst_path = os.path.join(
        VI_MASK_DIR, '{}_vegetation_cloud_mask.geojson'.format(period_s))
    run_command(
        '{gdal_bin_path}/gdal_polygonize.py {src} {dst} -b 1 -f "GeoJSON" DN'.
        format(gdal_bin_path=settings.GDAL_BIN_PATH,
               src=src_path,
               dst=dst_path))

    logging.info("Reproject to epsg:4326")
    data = gpd.read_file(dst_path)
    data_proj = data.copy()
    data_proj['geometry'] = data_proj['geometry'].to_crs(epsg=4326)
    data_proj.to_file(dst_path)

    logger.info("Load vegetation mask to DB")
    create_vegetation_masks(dst_path, period)


def create_vegetation_masks(geojson_path, period):
    ds = DataSource(geojson_path)
    vegetation_polys = []
    clouds_polys = []
    for x in range(0, len(ds[0]) - 1):
        geom = shapely.wkt.loads(ds[0][x].geom.wkt)
        if str(ds[0][x]['DN']) == '1':
            vegetation_polys.append(geom)
        elif str(ds[0][x]['DN']) == '2':
            clouds_polys.append(geom)
        else:
            pass
    vegetation_mp = unary_union(vegetation_polys)
    clouds_mp = unary_union(clouds_polys)

    Mask.objects.update_or_create(
        period=period,
        mask_type='ndvi',
        defaults=dict(geom=GEOSGeometry(vegetation_mp.wkt)))
    Mask.objects.update_or_create(
        period=period,
        mask_type='cloud',
        defaults=dict(geom=GEOSGeometry(clouds_mp.wkt)))


def generate_measurements(period):
    logger.info("Generate measurements for each scope")

    for scope in Scope.objects.all():
        mask = Mask.objects.filter(period=period, mask_type='ndvi').first()

        # TODO Optimize: use JOINs with Scope and Mask instead of building the shape WKT
        query = """
            SELECT ST_Area(a.int) AS area,
                   ST_Area(ST_Transform(ST_GeomFromText('{wkt_scope}', 4326), {srid})) as scope_area
            FROM (
                SELECT ST_Intersection(
                    ST_Transform(ST_GeomFromText('{wkt_scope}', 4326), {srid}),
                    ST_Transform(ST_GeomFromText('{wkt_mask}', 4326), {srid})) AS int) a;
            """.format(wkt_scope=scope.geom.wkt,
                       wkt_mask=mask.geom.wkt,
                       srid=32718)

        with connection.cursor() as cursor:
            cursor.execute(query)
            res = cursor.fetchall()
            area, scope_area = res[0]

        measurement, created = CoverageMeasurement.objects.update_or_create(
            date_from=period.date_from,
            date_to=period.date_to,
            scope=scope,
            defaults=dict(area=area, perc_area=area / scope_area))
        if created:
            logger.info(f"New measurement: {measurement}")


def run_command(cmd):
    logger.info(cmd)
    subprocess.run(cmd, shell=True, check=True)


def return_url(url):
    the_day_today = time.asctime().split()[0]
    the_hour_now = int(time.asctime().split()[3].split(":")[0])
    if the_day_today == "Wed" and 14 <= the_hour_now <= 17:
        logger.info("Sleeping for %d hours... Yawn!" % (18 - the_hour_now))
        time.sleep(60 * 60 * (18 - the_hour_now))

    req = urllib2.Request("%s" % (url), None, HEADERS)
    html = urllib2.urlopen(req).readlines()
    return html


def parse_modis_dates(url, dates, product, out_dir, ruff=False):
    """Parse returned MODIS dates.

    This function gets the dates listing for a given MODIS products, and
    extracts the dates for when data is available. Further, it crosses these
    dates with the required dates that the user has selected and returns the
    intersection. Additionally, if the `ruff` flag is set, we'll check for
    files that might already be present in the system and skip them. Note
    that if a file failed in downloading, it might still be around
    incomplete.

    Parameters
    ----------
    url: str
        A URL such as "http://e4ftl01.cr.usgs.gov/MOTA/MCD45A1.005/"
    dates: list
        A list of dates in the required format "YYYY.MM.DD"
    product: str
        The product name, MOD09GA.005
    out_dir: str
        The output dir
    ruff: bool
        Whether to check for present files
    Returns
    -------
    A (sorted) list with the dates that will be downloaded.
    """
    if ruff:
        product = product.split(".")[0]
        already_here = fnmatch.filter(os.listdir(out_dir), "%s*hdf" % product)
        already_here_dates = [x.split(".")[-5][1:] for x in already_here]

    html = return_url(url)

    available_dates = []
    for line in html:

        if line.decode().find("href") >= 0 and \
                        line.decode().find("[DIR]") >= 0:
            # Points to a directory
            the_date = line.decode().split('href="')[1].split('"')[0].strip(
                "/")
            if ruff:
                try:
                    modis_date = time.strftime(
                        "%Y%j", time.strptime(the_date, "%Y.%m.%d"))
                except ValueError:
                    continue
                if modis_date in already_here_dates:
                    continue
                else:
                    available_dates.append(the_date)
            else:
                available_dates.append(the_date)

    dates = set(dates)
    available_dates = set(available_dates)
    suitable_dates = list(dates.intersection(available_dates))
    suitable_dates.sort()
    return suitable_dates


def get_modisfiles(username,
                   password,
                   platform,
                   product,
                   year,
                   tile,
                   proxy,
                   doy_start=1,
                   doy_end=-1,
                   base_url="https://e4ftl01.cr.usgs.gov",
                   out_dir=".",
                   ruff=False,
                   get_xml=False,
                   verbose=False):
    """Download MODIS products for a given tile, year & period of interest

    This function uses the `urllib2` module to download MODIS "granules" from
    the USGS website. The approach is based on downloading the index files for
    any date of interest, and parsing the HTML (rudimentary parsing!) to search
    for the relevant filename for the tile the user is interested in. This file
    is then downloaded in the directory specified by `out_dir`.

    The function also checks to see if the selected remote file exists locally.
    If it does, it checks that the remote and local file sizes are identical.
    If they are, file isn't downloaded, but if they are different, the remote
    file is downloaded.

    Parameters
    ----------
    username: str
        The EarthData username string
    password: str
        The EarthData username string
    platform: str
        One of three: MOLA, MOLT MOTA
    product: str
        The product name, such as MOD09GA.005 or MYD15A2.005. Note that you
        need to specify the collection number (005 in the examples)
    year: int
        The year of interest
    tile: str
        The tile (e.g., "h17v04")
    proxy: dict
        A proxy definition, such as {'http': 'http://127.0.0.1:8080', \
        'ftp': ''}, etc.
    doy_start: int
        The starting day of the year.
    doy_end: int
        The ending day of the year.
    base_url: str, url
        The URL to use. Shouldn't be changed, unless USGS change the server.
    out_dir: str
        The output directory. Will be create if it doesn't exist
    ruff: Boolean
        Check to see what files are already available and download them without
        testing for file size etc.
    verbose: Boolean
        Whether to sprout lots of text out or not.
    get_xml: Boolean
        Whether to get the XML metadata files or not. Someone uses them,
        apparently ;-)
    Returns
    -------
    Nothing
    """

    if proxy is not None:
        proxy = urllib2.ProxyHandler(proxy)
        opener = urllib2.build_opener(proxy)
        urllib2.install_opener(opener)

    if not os.path.exists(out_dir):
        if verbose:
            logger.info("Creating output dir %s" % out_dir)
        os.makedirs(out_dir)
    if doy_end == -1:
        if calendar.isleap(year):
            doy_end = 367
        else:
            doy_end = 366

    dates = [
        time.strftime("%Y.%m.%d", time.strptime("%d/%d" % (i, year), "%j/%Y"))
        for i in range(doy_start, doy_end)
    ]
    url = "%s/%s/%s/" % (base_url, platform, product)
    dates = parse_modis_dates(url, dates, product, out_dir, ruff=ruff)

    # Only use the latests date from range
    dates = [dates[-1]]

    them_urls = []
    for date in dates:
        r = requests.get("%s%s" % (url, date), verify=False)
        for line in r.text.split("\n"):
            if line.find(tile) >= 0:
                if line.find(".hdf") >= 0:
                    fname = line.split("href=")[1].split(">")[0].strip('"')
                    if fname.endswith(".hdf.xml") and not get_xml:
                        pass
                    else:
                        if not os.path.exists(os.path.join(out_dir, fname)):
                            them_urls.append("%s/%s/%s" % (url, date, fname))
                        else:
                            if verbose:
                                logger.info(
                                    "File %s already present. Skipping" %
                                    fname)

    with requests.Session() as s:
        s.auth = (username, password)
        for the_url in them_urls:
            r1 = s.request('get', the_url)
            r = s.get(r1.url, stream=True)

            if not r.ok:
                raise IOError("Can't start download... [%s]" % the_url)
            file_size = int(r.headers['content-length'])
            fname = the_url.split("/")[-1]
            logger.info("Starting download on %s(%d bytes) ..." %
                        (os.path.join(out_dir, fname), file_size))
            with open(os.path.join(out_dir, fname), 'wb') as fp:
                for chunk in r.iter_content(chunk_size=CHUNKS):
                    if chunk:
                        fp.write(chunk)
                fp.flush()
                os.fsync(fp)
                if verbose:
                    logger.info("\tDone!")

    if verbose:
        logger.info("Completely finished downlading all there was")


def extract_subdatasets_as_gtiffs(out_dir, tif_dir):
    logger.info("Extract subdatasets as GeoTIFFs")
    for f in os.listdir(out_dir):
        if f.endswith('.hdf'):
            src = os.path.join(out_dir, f)
            dst = os.path.join(tif_dir, f)
            if not os.path.exists(f'{dst}_ndvi.tif'):
                run_command(
                    f'gdal_translate HDF4_EOS:EOS_GRID:{src}:MODIS_Grid_16DAY_250m_500m_VI:"250m 16 days NDVI" {dst}_ndvi.tif'
                )
            if not os.path.exists(f'{dst}_pixelrel.tif'):
                run_command(
                    f'gdal_translate HDF4_EOS:EOS_GRID:{src}:MODIS_Grid_16DAY_250m_500m_VI:"250m 16 days pixel reliability" {dst}_pixelrel.tif'
                )


def clean_temp_files():
    logger.info("Clean temporary files")
    shutil.rmtree(VI_CLIP_DIR)
    #shutil.rmtree(VI_RAW_DIR)
    shutil.rmtree(VI_TIF_DIR)
