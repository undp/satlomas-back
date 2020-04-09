import calendar
import fnmatch
import logging
import os
import shutil
import subprocess
import sys
import time

import django_rq
import geopandas as gpd
import numpy as np
import rasterio
import requests
from django.conf import settings
from django_rq import job
from requests.packages.urllib3.exceptions import InsecureRequestWarning

from vi_lomas_changes.models import VegetationMask

try:
    import urllib.request as urllib2
except ImportError:
    import urllib2

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

LOG = logging.getLogger(__name__)
OUT_HDLR = logging.StreamHandler(sys.stdout)
OUT_HDLR.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
OUT_HDLR.setLevel(logging.INFO)
LOG.addHandler(OUT_HDLR)
LOG.setLevel(logging.INFO)

HEADERS = {'User-Agent': 'get_modis Python 3'}
CHUNKS = 65536

MODIS_PLATFORM = 'MOLA'
MODIS_PRODUCT = 'MYD13Q1.006'
MODIS_ROOT = os.path.join(settings.BASE_DIR, 'modis')
MODIS_OUT_DIR = os.path.join(MODIS_ROOT, 'out')
MODIS_TIF_DIR = os.path.join(MODIS_ROOT, 'tif')
MODIS_CLIP_DIR = os.path.join(MODIS_ROOT, 'clip')
VEGETATION_MASK_DIR = os.path.join('data', 'vegetation')
H_PERU = '10'
V_PERU = '10'


def run_subprocess(cmd):
    print(cmd)
    subprocess.run(cmd, shell=True, check=True)


def return_url(url):
    the_day_today = time.asctime().split()[0]
    the_hour_now = int(time.asctime().split()[3].split(":")[0])
    if the_day_today == "Wed" and 14 <= the_hour_now <= 17:
        LOG.info("Sleeping for %d hours... Yawn!" % (18 - the_hour_now))
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
            LOG.info("Creating outupt dir %s" % out_dir)
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
                                LOG.info("File %s already present. Skipping" %
                                         fname)

    # si el vector tiene al menos una url (longitud > 0)
    if len(them_urls) > 0:
        them_urls = [them_urls[-1]]  # me quedo con el ultimo producto
    # si el vector esta vacio lo que sigue no hace nada

    with requests.Session() as s:
        s.auth = (username, password)
        for the_url in them_urls:
            r1 = s.request('get', the_url)
            r = s.get(r1.url, stream=True)

            if not r.ok:
                raise IOError("Can't start download... [%s]" % the_url)
            file_size = int(r.headers['content-length'])
            fname = the_url.split("/")[-1]
            LOG.info("Starting download on %s(%d bytes) ..." %
                     (os.path.join(out_dir, fname), file_size))
            with open(os.path.join(out_dir, fname), 'wb') as fp:
                for chunk in r.iter_content(chunk_size=CHUNKS):
                    if chunk:
                        fp.write(chunk)
                fp.flush()
                os.fsync(fp)
                if verbose:
                    LOG.info("\tDone!")
    if verbose:
        LOG.info("Completely finished downlading all there was")


def gdal_translate(out_dir, tif_dir):
    for f in os.listdir(out_dir):
        if f.endswith('.hdf'):
            cmd = 'gdal_translate HDF4_EOS:EOS_GRID:{}:MODIS_Grid_16DAY_250m_500m_VI:"250m 16 days NDVI" {}_ndvi.tif'.format(
                os.path.join(out_dir, f), os.path.join(tif_dir, f))
            print('Ejecutando {}'.format(cmd))
            rv = os.system(cmd)
            cmd = 'gdal_translate HDF4_EOS:EOS_GRID:{}:MODIS_Grid_16DAY_250m_500m_VI:"250m 16 days pixel reliability" {}_pixelrel.tif'.format(
                os.path.join(out_dir, f), os.path.join(tif_dir, f))
            print('Ejecutando {}'.format(cmd))
            rv = os.system(cmd)


@job("default", timeout=3600)
def get_modis_peru(date_from, date_to):
    year = date_to.year
    doy_begin = date_from.timetuple().tm_yday
    doy_end = date_to.timetuple().tm_yday

    os.makedirs(MODIS_OUT_DIR, exist_ok=True)
    os.makedirs(MODIS_TIF_DIR, exist_ok=True)

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
                   out_dir=MODIS_OUT_DIR,
                   verbose=True,
                   ruff=False,
                   get_xml=False)

    gdal_translate(MODIS_OUT_DIR, MODIS_TIF_DIR)

    django_rq.enqueue('vegetation.tasks.vegetation_mask', date_from, date_to)


@job("default", timeout=3600)
def vegetation_mask(date_from, date_to):
    area_monitoreo = os.path.join(settings.BASE_DIR, 'data',
                                  'area_monitoreo.geojson')
    srtm_dem = os.path.join(settings.BASE_DIR, 'data', 'srtm_dem.tif')
    srtm_monitoreo = os.path.join(settings.BASE_DIR, 'data',
                                  'srtm_dem_monitoreo.tif')
    if not os.path.exists(srtm_monitoreo):
        run_subprocess(
            '{gdal_bin_path}/gdalwarp -of GTiff -cutline {aoi} -crop_to_cutline {src} {dst}'
            .format(gdal_bin_path=settings.GDAL_BIN_PATH,
                    aoi=area_monitoreo,
                    src=srtm_dem,
                    dst=srtm_monitoreo))

    os.makedirs(MODIS_CLIP_DIR, exist_ok=True)

    with rasterio.open(srtm_monitoreo) as srtm_src:
        srtm = srtm_src.read(1)

        LOMAS_MIN = 200
        LOMAS_MAX = 1800
        lomas_mask = ((srtm >= LOMAS_MIN) & (srtm <= LOMAS_MAX))

    FACTOR_ESCALA = 0.0001
    UMBRAL_NDVI = 0.2
    tope = UMBRAL_NDVI / FACTOR_ESCALA

    f = '*h10v10*.hdf_ndvi.tif'
    ndvi = os.path.join(MODIS_TIF_DIR, f)
    ndvi_monitoreo = os.path.join(MODIS_CLIP_DIR, f)
    run_subprocess(
        '{gdal_bin_path}/gdalwarp -of GTiff -cutline {aoi} -crop_to_cutline $(ls {src}) {dst}'
        .format(gdal_bin_path=settings.GDAL_BIN_PATH,
                aoi=area_monitoreo,
                src=ndvi,
                dst=ndvi_monitoreo))

    run_subprocess(
        '{otb_bin_path}/otbcli_Superimpose -inr {inr} -inm {inm} -out {out}'.
        format(otb_bin_path=settings.OTB_BIN_PATH,
               inr=srtm_monitoreo,
               inm=ndvi_monitoreo,
               out=ndvi_monitoreo))

    with rasterio.open(ndvi_monitoreo) as modis_ndvi_src:
        modis_ndvi = modis_ndvi_src.read(1)

        vegetacion_mask = (modis_ndvi > tope)

        verde_mask = (vegetacion_mask & lomas_mask)
        verde = np.copy(modis_ndvi)
        verde[~verde_mask] = 0

        verde_rango = np.copy(verde)
        verde_rango[(verde >= (0.2 / FACTOR_ESCALA))
                    & (verde < (0.4 / FACTOR_ESCALA))] = 1
        verde_rango[(verde >= (0.4 / FACTOR_ESCALA))
                    & (verde < (0.6 / FACTOR_ESCALA))] = 2
        verde_rango[(verde >= (0.6 / FACTOR_ESCALA))
                    & (verde < (0.8 / FACTOR_ESCALA))] = 3
        verde_rango[verde >= (0.8 / FACTOR_ESCALA)] = 4

        verde[verde_mask] = 1

        modis_meta = modis_ndvi_src.profile

        period = "{}{}-{}{}".format(
            ("0" + str(date_from.month))[-2:], date_from.year,
            ("0" + str(date_to.month))[-2:], date_to.year)

        os.makedirs(VEGETATION_MASK_DIR, exist_ok=True)

        dst_name = os.path.join(VEGETATION_MASK_DIR,
                                '{}-vegetation_mask.tif'.format(period))
        with rasterio.open(dst_name, 'w', **modis_meta) as dst:
            dst.write(verde, 1)

        #Cloud mask
        f = '*h10v10*.hdf_pixelrel.tif'
        pixelrel = os.path.join(MODIS_TIF_DIR, f)
        pixelrel_monitoreo = os.path.join(MODIS_CLIP_DIR, f)
        run_subprocess(
            '{gdal_bin_path}/gdalwarp -of GTiff -cutline {aoi} -crop_to_cutline $(ls {src}) {dst}'
            .format(gdal_bin_path=settings.GDAL_BIN_PATH,
                    aoi=area_monitoreo,
                    src=pixelrel,
                    dst=pixelrel_monitoreo))
        run_subprocess(
            '{otb_bin_path}/otbcli_Superimpose -inr {inr} -inm {inm} -out {out}'
            .format(otb_bin_path=settings.OTB_BIN_PATH,
                    inr=srtm_monitoreo,
                    inm=pixelrel_monitoreo,
                    out=pixelrel_monitoreo))
        with rasterio.open(pixelrel_monitoreo) as cloud_src:
            clouds = cloud_src.read(1)
        #In clouds 2 is snow/ice and 3 are clouds, and -1 is not processed data
        cloud_mask = np.copy(clouds)
        cloud_mask[(clouds == 2) | (clouds == 3) | (clouds == -1)] = 1
        cloud_mask[(clouds != 2) & (clouds != 3)] = 0

        dst_name = os.path.join(VEGETATION_MASK_DIR,
                                '{}-cloud_mask.tif'.format(period))
        with rasterio.open(dst_name, 'w', **modis_meta) as dst:
            dst.write(cloud_mask, 1)

        modis_meta['dtype'] = "float32"
        dst_name = os.path.join(VEGETATION_MASK_DIR,
                                '{}-vegetation_range.tif'.format(period))
        with rasterio.open(dst_name, 'w', **modis_meta) as dst:
            dst.write(verde_rango, 1)

        #Create a mask with data from vegetation and clouds
        verde[cloud_mask == 1] = 2
        dst_name = os.path.join(VEGETATION_MASK_DIR,
                                '{}-vegetation_cloud_mask.tif'.format(period))
        with rasterio.open(dst_name, 'w', **modis_meta) as dst:
            dst.write(verde, 1)
        #Create poligons from the mask
        output_name = os.path.join(
            VEGETATION_MASK_DIR,
            '{}-vegetation_cloud_geom.geojson'.format(period))
        run_subprocess(
            '{gdal_bin_path}/gdal_polygonize.py {tif_src} {geojson_output} -b 1 -f "GeoJSON" DN'
            .format(gdal_bin_path=settings.GDAL_BIN_PATH,
                    tif_src=dst_name,
                    geojson_output=output_name))

        data = gpd.read_file(output_name)
        data_proj = data.copy()
        data_proj['geometry'] = data_proj['geometry'].to_crs(epsg=32718)
        data_proj.to_file(output_name)

        VegetationMask.save_from_geojson(output_name, date_from)

    shutil.rmtree(MODIS_CLIP_DIR)
    shutil.rmtree(MODIS_OUT_DIR)
    shutil.rmtree(MODIS_TIF_DIR)
