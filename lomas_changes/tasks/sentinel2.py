import json
import os
import shutil
import subprocess
from pathlib import Path
from zipfile import ZipFile
from glob import glob

from django.conf import settings
from sentinelsat.sentinel import SentinelAPI, geojson_to_wkt, read_geojson

import lomas_changes
from lomas_changes.utils import run_subprocess

APPDIR = os.path.dirname(lomas_changes.__file__)

S2_L1C_PATH = os.path.join(settings.BASE_DIR, 'data', 'images', 's2', 'l1c')
S2_L2A_PATH = os.path.join(settings.BASE_DIR, 'data', 'images', 's2', 'l2a')
AOI_PATH = os.path.join(APPDIR, 'data', 'extent.geojson')


def download_scenes(period):
    date_from = period.date_from
    date_to = period.date_to

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
                         cloudcoverpercentage=(0, 100))

    # Skip L2A products
    l2 = []
    for p in products:
        if 'MSIL2A' in products[p]['title']:
            l2.append(p)
    for p in l2:
        products.pop(p)

    for p in products:
        print(products[p]['title'])

    os.makedirs(S2_L1C_PATH, exist_ok=True)

    # Filter already downloaded products
    products_to_download = {
        k: v
        for k, v in products.items() if not os.path.exists(
            os.path.join(S2_L1C_PATH, '{}.zip'.format(v['title'])))
    }

    # Download products
    results = api.download_all(products, directory_path=S2_L1C_PATH)
    products = list(products.values())

    # Unzip
    for p in products:
        unzip_product(p)

    # Get the list of L1C products still to be processed to L2A
    l1c_can_prods = get_canonical_names(
        glob(os.path.join(S2_L1C_PATH, '*.SAFE')))
    l2a_can_prods = get_canonical_names(
        glob(os.path.join(S2_L2A_PATH, '*.SAFE')))
    missing_l1c_prods = [
        l1c_can_prods[k]
        for k in set(l1c_can_prods.keys()) - set(l2a_can_prods.keys())
    ]

    # Create symbolic links for products that need to be processed
    wip_dir = os.path.join(S2_L1C_PATH, 'wip')
    if os.path.exists(wip_dir):
        shutil.rmtree(wip_dir)
    os.makedirs(os.path.join(S2_L1C_PATH, 'wip'))
    for p in missing_l1c_prods:
        name = os.path.basename(p)
        os.symlink(p, os.path.join(wip_dir, name))

    # Run s2m preprocess (sen2cor) on raw directory
    # s2m preprocess -res 20 /path/to/DATA_dir/
    cmd = "python3 {}/preprocess.py -v -p {} -o {} {}".format(
        settings.S2M_CLI_PATH, settings.S2M_NUM_JOBS, S2_L2A_PATH, wip_dir)
    rv = os.system(cmd)
    if rv != 0:
        raise ValueError('s2m preprocess failed')

    shutil.rmtree(wip_dir)

    # Obtain necesary gdal info
    gdal_info = False
    for item in os.listdir(S2_L2A_PATHS):
        if item.startswith("S2B_MSIL2A") and item.endswith(".SAFE"):
            info = None
            for filename in Path(os.path.join(
                    S2_L2A_PATH, item)).rglob("*/IMG_DATA/R20m/*.jp2"):
                print("get info from {}".format(filename))
                info = subprocess.getoutput(
                    "gdalinfo -json {}".format(filename))
                break

            if info == None:
                print("No GDAL info found on this folder.")
                continue
            else:
                gdal_info = True
                info = json.loads(info)
                print(info)
                print(info["cornerCoordinates"]["upperLeft"])
                print(info["cornerCoordinates"]["lowerRight"])

                xmin = min(info["cornerCoordinates"]["upperLeft"][0],
                           info["cornerCoordinates"]["lowerRight"][0])
                ymin = min(info["cornerCoordinates"]["upperLeft"][1],
                           info["cornerCoordinates"]["lowerRight"][1])
                xmax = max(info["cornerCoordinates"]["upperLeft"][0],
                           info["cornerCoordinates"]["lowerRight"][0])
                ymax = max(info["cornerCoordinates"]["upperLeft"][1],
                           info["cornerCoordinates"]["lowerRight"][1])
                break

    # Build mosaic
    if gdal_info:
        mosaic_path = os.path.join(settings.IMAGES_PATH, 'mosaic')
        os.makedirs(mosaic_path, exist_ok=True)

        mosaic_name = '{}{}_{}{}_mosaic.tif'.format(date_from.year,
                                                    date_from.month,
                                                    date_to.year,
                                                    date_to.month)
        cmd = "python3 {}/mosaic.py -te {} {} {} {} -e 32718 -res 20 -n {} -v -o {} {}".format(
            settings.S2M_CLI_PATH, xmin, ymin, xmax, ymax, mosaic_name,
            mosaic_path, S2_L2A_PATHS)
        rv = os.system(cmd)
        if rv != 0:
            raise ValueError('s2m mosaic failed for {}.'.format(item))

        cmd = "python3 {}/mosaic.py -te {} {} {} {} -e 32718 -res 10 -n {} -v -o {} {}".format(
            settings.S2M_CLI_PATH, xmin, ymin, xmax, ymax, mosaic_name,
            mosaic_path, S2_L2A_PATH)
        rv = os.system(cmd)
        if rv != 0:
            raise ValueError('s2m mosaic failed for {}.'.format(item))

        #delete useless products
        #shutil.rmtree(S2_L1C_PATH)
        #shutil.rmtree(S2_L2A_PATH)

        generate_vegetation_indexes(mosaic_name)
        concatenate_results(mosaic_name, date_from, date_to)
        clip_results(date_from, date_to)
        period.s2_finished = True
        period.save()

        if period.s1_finished:
            django_rq.enqueue('lomas_changes.tasks.predict_rf.predict_rf',
                              period)

    else:
        print("No GDAL info found on raw folder.")


def unzip_product(product):
    print("### Unzip", product['title'])
    filename = '{}.zip'.format(product['title'])
    zip_path = os.path.join(S2_L1C_PATH, filename)
    outdir = os.path.join(S2_L1C_PATH, '{}.SAFE'.format(product['title']))
    if not os.path.exists(outdir):
        unzip(zip_path, delete_zip=False)


def generate_vegetation_indexes(mosaic_name):
    mosaic_path = os.path.join(settings.IMAGES_PATH, 'mosaic')
    nir = os.path.join(mosaic_path, '{}_R10m_NIR.vrt'.format(mosaic_name))
    rgb = os.path.join(mosaic_path, '{}_R10m_RGB.vrt'.format(mosaic_name))

    #ndiv
    dst = os.path.join(mosaic_path, 'R10m_NDVI.tif')
    exp = '(im1b1 - im2b1) / (im1b1 + im2b1)'
    run_subprocess(
        '{otb_bin_path}/otbcli_BandMath -il {nir} {rgb} -out {dst} -exp "{exp}"'
        .format(otb_bin_path=settings.OTB_BIN_PATH,
                nir=nir,
                rgb=rgb,
                dst=dst,
                exp=exp))

    #ndwi
    dst = os.path.join(mosaic_path, 'R10m_NDWI.tif')
    exp = '(im1b1 - im2b2) / (im1b1 + im2b2)'
    run_subprocess(
        '{otb_bin_path}/otbcli_BandMath -il {nir} {rgb} -out {dst} -exp "{exp}"'
        .format(otb_bin_path=settings.OTB_BIN_PATH,
                nir=nir,
                rgb=rgb,
                dst=dst,
                exp=exp))

    #evi
    dst = os.path.join(mosaic_path, 'R10m_EVI.tif')
    exp = '(2.5 * ((im1b1 - im2b1) / (im1b1 + 6 * im2b1 - 7.5 * im2b3 + 1)))'
    run_subprocess(
        '{otb_bin_path}/otbcli_BandMath -il {nir} {rgb} -out {dst} -exp "{exp}"'
        .format(otb_bin_path=settings.OTB_BIN_PATH,
                nir=nir,
                rgb=rgb,
                dst=dst,
                exp=exp))

    #savi
    dst = os.path.join(mosaic_path, 'R10m_SAVI.tif')
    exp = '((im1b1 - im2b1) * 1.5 / (im1b1 + im2b1 + 0.5))'
    run_subprocess(
        '{otb_bin_path}/otbcli_BandMath -il {nir} {rgb} -out {dst} -exp "{exp}"'
        .format(otb_bin_path=settings.OTB_BIN_PATH,
                nir=nir,
                rgb=rgb,
                dst=dst,
                exp=exp))


def concatenate_results(mosaic_name, date_from, date_to):
    mosaic_path = os.path.join(settings.IMAGES_PATH, 'mosaic')
    tif_10m = 's2_{}{}_{}{}_10m.tif'.format(date_from.year, date_from.month,
                                            date_to.year, date_to.month)
    tif_20m = 's2_{}{}_{}{}_20m.tif'.format(date_from.year, date_from.month,
                                            date_to.year, date_to.month)

    R10m_B02 = os.path.join(mosaic_path, '{}_R10m_B02.tif'.format(mosaic_name))
    R10m_B03 = os.path.join(mosaic_path, '{}_R10m_B03.tif'.format(mosaic_name))
    R10m_B04 = os.path.join(mosaic_path, '{}_R10m_B04.tif'.format(mosaic_name))
    R10m_B08 = os.path.join(mosaic_path, '{}_R10m_B08.tif'.format(mosaic_name))
    R10m_NDVI = os.path.join(mosaic_path, 'R10m_NDVI.tif')
    R10m_NDVI = os.path.join(mosaic_path, 'R10m_NDWI.tif')
    R10m_EVI = os.path.join(mosaic_path, 'R10m_EVI.tif')
    R10m_SAVI = os.path.join(mosaic_path, 'R10m_SAVI.tif')
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


def clip_results(date_from, date_to):
    mosaic_path = os.path.join(settings.IMAGES_PATH, 'mosaic')
    results_src = os.path.join(settings.BASE_DIR, 'data', 'images', 'results',
                               'src')
    tif_10m = 's2_{}{}_{}{}_10m.tif'.format(date_from.year, date_from.month,
                                            date_to.year, date_to.month)
    tif_20m = 's2_{}{}_{}{}_20m.tif'.format(date_from.year, date_from.month,
                                            date_to.year, date_to.month)

    srcs = [tif_10m, tif_20m]

    for src in srcs:
        run_subprocess(
            '{gdal_bin_path}/gdalwarp -of GTiff -cutline {aoi} -crop_to_cutline {src} {dst}'
            .format(gdal_bin_path=settings.GDAL_BIN_PATH,
                    aoi=AOI_PATH,
                    src=os.path.join(mosaic_path, src),
                    dst=os.path.join(results_src, src)))


def get_canonical_names(prods):
    r = [os.path.basename(p) for p in prods]
    r = [n.split('_') for n in r]
    r = ["_".join([ps[i] for i in [0, 2, 4, 5]]) for ps in r]
    return dict(zip(r, prods))
