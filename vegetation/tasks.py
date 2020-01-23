import os
try:
    import urllib.request as urllib2
except ImportError:
    import urllib2
import time
import calendar
import logging
import sys
import fnmatch
import requests
from django.conf import settings
from django_rq import job
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

LOG = logging.getLogger( __name__ )
OUT_HDLR = logging.StreamHandler( sys.stdout )
OUT_HDLR.setFormatter( logging.Formatter( '%(asctime)s %(message)s') )
OUT_HDLR.setLevel( logging.INFO )
LOG.addHandler( OUT_HDLR )
LOG.setLevel( logging.INFO )

HEADERS = { 'User-Agent' : 'get_modis Python 3'}
CHUNKS = 65536

MODIS_PLATFORM = 'MOLA'
MODIS_PRODUCT = 'MYD13Q1.006'
MODIS_ROOT = os.path.join(settings.BASE_DIR, 'modis')
MODIS_OUT_DIR = os.path.join(MODIS_ROOT,'out')
MODIS_TIF_DIR = os.path.join(MODIS_ROOT,'tif')
MODIS_CLIP_DIR = os.path.join(MODIS_ROOT, 'clip')
H_PERU = ['09', '10', '11']
V_PERU = ['09', '10', '11']


def return_url(url):
    the_day_today = time.asctime().split()[0]
    the_hour_now = int(time.asctime().split()[3].split(":")[0])
    if the_day_today == "Wed" and 14 <= the_hour_now <= 17:
        LOG.info("Sleeping for %d hours... Yawn!" % (18 - the_hour_now))
        time.sleep(60 * 60 * (18 - the_hour_now))

    req = urllib2.Request("%s" % (url), None, HEADERS)
    html = urllib2.urlopen(req).readlines()
    return html


def parse_modis_dates ( url, dates, product, out_dir, ruff=False ):
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
        already_here = fnmatch.filter(os.listdir(out_dir),
                                      "%s*hdf" % product)
        already_here_dates = [x.split(".")[-5][1:]
                              for x in already_here]

    html = return_url(url)

    available_dates = []
    for line in html:

        if line.decode().find("href") >= 0 and \
                        line.decode().find("[DIR]") >= 0:
            # Points to a directory
            the_date = line.decode().split('href="')[1].split('"')[0].strip("/")
            if ruff:
                try:
                    modis_date = time.strftime("%Y%j",
                                               time.strptime(the_date,
                                                             "%Y.%m.%d"))
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


def get_modisfiles(username, password, platform, product, year, tile, proxy,
                   doy_start=1, doy_end=-1,
                   base_url="https://e4ftl01.cr.usgs.gov", out_dir=".",
                   ruff=False, get_xml=False, verbose=False):

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

    dates = [time.strftime("%Y.%m.%d", time.strptime("%d/%d" % (i, year),
                                                     "%j/%Y")) for i in
             range(doy_start, doy_end)]
    url = "%s/%s/%s/" % (base_url, platform, product)
    dates = parse_modis_dates(url, dates, product, out_dir, ruff=ruff)
    them_urls = []
    for date in dates:
        r = requests.get("%s%s" % (url, date), verify=False)
        for line in r.text.split("\n"):
            if line.find(tile) >= 0:
                if line.find(".hdf")  >= 0:
                    fname = line.split("href=")[1].split(">")[0].strip('"')
                    if fname.endswith(".hdf.xml") and not get_xml:
                        pass
                    else:
                        if not os.path.exists(os.path.join(out_dir, fname)):
                            them_urls.append("%s/%s/%s" % (url, date, fname))
                        else:
                            if verbose:
                                LOG.info("File %s already present. Skipping" % fname)

    # si el vector tiene al menos una url (longitud > 0)
    if len(them_urls) > 0:
        them_urls = [ them_urls[-1] ] # me quedo con el ultimo producto
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
            cmd = 'gdal_translate HDF4_EOS:EOS_GRID:{}:MODIS_Grid_16DAY_250m_500m_VI:"250m 16 days NDVI" {}_ndvi.tif'.format(os.path.join(out_dir, f), os.path.join(tif_dir, f))
            print('Ejecutando {}'.format(cmd))
            rv = os.system(cmd)
            cmd = 'gdal_translate HDF4_EOS:EOS_GRID:{}:MODIS_Grid_16DAY_250m_500m_VI:"250m 16 days pixel reliability" {}_pixelrel.tif'.format(os.path.join(out_dir, f), os.path.join(tif_dir, f))
            print('Ejecutando {}'.format(cmd))
            rv = os.system(cmd)


@job("default", timeout=3600)
def get_modis_peru(date_from, date_to):
    year = date_to.year
    doy_begin = date_from.timetuple().tm_yday
    doy_end = date_to.timetuple().tm_yday

    os.makedirs(MODIS_OUT_DIR, exist_ok=True)
    os.makedirs(MODIS_TIF_DIR, exist_ok=True)

    for h in H_PERU:
        for v in V_PERU:
            tile = 'h{}v{}'.format(h, v)

            get_modisfiles(
                settings.MODIS_USER, settings.MODIS_PASS, 
                MODIS_PLATFORM, MODIS_PRODUCT,
                year, tile, proxy=None,
                doy_start=doy_begin, doy_end=doy_end,
                out_dir=MODIS_OUT_DIR,
                verbose=True, ruff=False,
                get_xml=False)

    gdal_translate(MODIS_OUT_DIR, MODIS_TIF_DIR)


def vegetation_mask():
    area_monitoreo = os.path.join(settings.BASE_DIR, 'data', 'area_monitoreo_4326_b250.geojson')
    srtm = os.path.join(settings.BASE_DIR, 'data', 'srtm_dem.tif')
    srtm_monitoreo = os.path.join(settings.BASE_DIR, 'data', 'srtm_dem_monitoreo.tif')
    run_subprocess('{gdal_bin_path}/gdalwarp -of GTiff -cutline {aoi} -crop_to_cutline {src} {dst}'.format(
        gdal_bin_path=settings.GDAL_BIN_PATH,
        aoi=area_monitoreo,
        src=srtm,
        dst=srtm_monitoreo))

    os.makedirs(MODIS_CLIP_DIR, exist_ok=True)

    for f in os.listdir(MODIS_TIF_DIR):
        if f.endswith('_ndvi.tif'):
            ndvi = os.path.join(MODIS_TIF_DIR, f)
            ndvi_monitoreo = os.path.join(MODIS_CLIP_DIR, f) 
            run_subprocess('{gdal_bin_path}/gdalwarp -of GTiff -cutline {aoi} -crop_to_cutline {src} {dst}'.format(
                gdal_bin_path=settings.GDAL_BIN_PATH,
                aoi=area_monitoreo,
                src=ndvi,
                dst=ndvi_monitoreo))
