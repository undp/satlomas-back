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
import rasterio
import requests
from django.conf import settings
from requests.packages.urllib3.exceptions import InsecureRequestWarning

import vi_lomas_changes
from vi_lomas_changes.models import VegetationMask

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


def get_modis_peru(date_from, date_to):
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

    logger.info("Extract subdatasets as GeoTIFFs")
    gdal_translate(VI_RAW_DIR, VI_TIF_DIR)

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
        modis_meta = src.profile

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

    verde[verde_mask] = 1

    period = "{}{}-{}{}".format(("0" + str(date_from.month))[-2:],
                                date_from.year,
                                ("0" + str(date_to.month))[-2:], date_to.year)

    logger.info("Write vegetation mask")
    os.makedirs(VI_MASK_DIR, exist_ok=True)
    dst_name = os.path.join(VI_MASK_DIR,
                            '{}-vegetation_mask.tif'.format(period))
    with rasterio.open(dst_name, 'w', **modis_meta) as dst:
        dst.write(verde, 1)

    # Cloud mask
    logger.info("Clip pixel reliability raster to extent")
    pixelrel_path = glob(os.path.join(VI_TIF_DIR, '*h10v10*.hdf_pixelrel.tif'))[0]
    pixelrel_clipped_path = os.path.join(VI_CLIP_DIR, os.path.basename(pixelrel_path))
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

    dst_name = os.path.join(VI_MASK_DIR, '{}-cloud_mask.tif'.format(period))
    with rasterio.open(dst_name, 'w', **modis_meta) as dst:
        dst.write(cloud_mask, 1)

    modis_meta['dtype'] = "float32"
    dst_name = os.path.join(VI_MASK_DIR,
                            '{}-vegetation_range.tif'.format(period))
    with rasterio.open(dst_name, 'w', **modis_meta) as dst:
        dst.write(verde_rango, 1)

    # FIXME Write this mask as a temporary file
    logger.info("Create a mask with data from vegetation and clouds")
    verde[cloud_mask == 1] = 2
    dst_name = os.path.join(VI_MASK_DIR,
                            '{}-vegetation_cloud_mask.tif'.format(period))
    with rasterio.open(dst_name, 'w', **modis_meta) as dst:
        dst.write(verde, 1)

    logger.info("Create poligons from the mask")
    output_name = os.path.join(
        VI_MASK_DIR, '{}-vegetation_cloud_geom.geojson'.format(period))
    run_command(
        '{gdal_bin_path}/gdal_polygonize.py {tif_src} {geojson_output} -b 1 -f "GeoJSON" DN'
        .format(gdal_bin_path=settings.GDAL_BIN_PATH,
                tif_src=dst_name,
                geojson_output=output_name))

    logger.info("Load vegetation mask to DB") 
    data = gpd.read_file(output_name)
    data_proj = data.copy()
    data_proj['geometry'] = data_proj['geometry'].to_crs(epsg=32718)
    data_proj.to_file(output_name)

    VegetationMask.save_from_geojson(output_name, date_from)

    # TODO Load Rasters for: vegetation_range, cloud_mask

    clean_temp_files()


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


def gdal_translate(out_dir, tif_dir):
    for f in os.listdir(out_dir):
        if f.endswith('.hdf'):
            src = os.path.join(out_dir, f)
            dst = os.path.join(tif_dir, f)
            run_command(
                f'gdal_translate HDF4_EOS:EOS_GRID:{src}:MODIS_Grid_16DAY_250m_500m_VI:"250m 16 days NDVI" {dst}_ndvi.tif'
            )
            run_command(
                f'gdal_translate HDF4_EOS:EOS_GRID:{src}:MODIS_Grid_16DAY_250m_500m_VI:"250m 16 days pixel reliability" {dst}_pixelrel.tif'
            )


def clean_temp_files():
    logger.info("Clean temporary files")
    shutil.rmtree(VI_CLIP_DIR)
    #shutil.rmtree(VI_RAW_DIR)
    shutil.rmtree(VI_TIF_DIR)
