import os
import shutil
from datetime import date

import dateutil.relativedelta
import django_rq
import numpy as np
import rasterio
from django.conf import settings
from sentinelsat.sentinel import SentinelAPI, geojson_to_wkt, read_geojson

import lomas_changes
from lomas_changes.models import Period, Product
from lomas_changes.tasks import predict_rf
from lomas_changes.utils import run_subprocess, sliding_windows, unzip

APPDIR = os.path.dirname(lomas_changes.__file__)

S1_RAW_PATH = os.path.join(settings.BASE_DIR, 'data', 'images', 's1', 'raw')
S1_RES_PATH = os.path.join(settings.BASE_DIR, 'data', 'images', 's1',
                           'results')

AOI_PATH = os.path.join(APPDIR, 'data', 'extent.geojson')


def download_scenes(period):
    init_date = period.init_date
    end_date = period.end_date

    api = SentinelAPI(settings.SCIHUB_USER, settings.SCIHUB_PASS,
                      settings.SCIHUB_URL)

    footprint = geojson_to_wkt(read_geojson(AOI_PATH))
    products = api.query(footprint,
                         date=(init_date, end_date),
                         platformname='Sentinel-1',
                         producttype='GRD',
                         polarisationmode='VV VH',
                         orbitdirection='ASCENDING')

    for k, p in products.items():
        print((k, p['summary']))

    os.makedirs(S1_RAW_PATH, exist_ok=True)

    # Filter already downloaded products
    products_to_download = {
        k: v
        for k, v in products.items() if not os.path.exists(
            os.path.join(S1_RAW_PATH, '{}.zip'.format(v['title'])))
    }
    # Download products
    results = api.download_all(products_to_download,
                               directory_path=S1_RAW_PATH)
    products = list(products.values())

    # Process the images of each product
    for p in products:
        unzip_product(p)
        calibrate(p)
        despeckle(p)
        clip(p)
        concatenate(p)

    # Create a median composite from all images of each band, generate extra
    # bands and concatenate results into a single multiband imafge.
    superimpose(products)
    median(products, period)
    generate_vvvh(period)
    concatenate_results(period)
    clip_result(period)


def unzip_product(product):
    print("### Unzip", product['title'])
    filename = '{}.zip'.format(product['title'])
    zip_path = os.path.join(S1_RAW_PATH, filename)
    outdir = os.path.join(S1_RAW_PATH, '{}.SAFE'.format(product['title']))
    if not os.path.exists(outdir):
        unzip(zip_path, delete_zip=False)


def calibrate(product):
    print("# Calibrate", product['title'])
    name = '{}.SAFE'.format(product['title'])

    dst_folder = os.path.join(S1_RAW_PATH, 'proc', name, 'calib')
    os.makedirs(dst_folder, exist_ok=True)

    src = os.path.join(S1_RAW_PATH, name, 'measurement', '*-vv-*.tiff')
    dst = os.path.join(dst_folder, 'vv.tiff')
    if not os.path.exists(dst):
        run_subprocess(
            '{otb_bin_path}/otbcli_SARCalibration -in $(ls {src}) -out {dst}'.
            format(otb_bin_path=settings.OTB_BIN_PATH, src=src, dst=dst))

    src = os.path.join(S1_RAW_PATH, name, 'measurement', '*-vh-*.tiff')
    dst = os.path.join(dst_folder, 'vh.tiff')
    if not os.path.exists(dst):
        run_subprocess(
            '{otb_bin_path}/otbcli_SARCalibration -in $(ls {src}) -out {dst}'.
            format(otb_bin_path=settings.OTB_BIN_PATH, src=src, dst=dst))


def despeckle(product):
    print("# Despeckle", product['title'])
    name = '{}.SAFE'.format(product['title'])

    dst_folder = os.path.join(S1_RAW_PATH, 'proc', name, 'despeck')
    os.makedirs(dst_folder, exist_ok=True)

    src = os.path.join(S1_RAW_PATH, 'proc', name, 'calib', 'vv.tiff')
    dst = os.path.join(dst_folder, 'vv.tiff')
    if not os.path.exists(dst):
        run_subprocess(
            '{otb_bin_path}/otbcli_Despeckle -in {src} -out {dst}'.format(
                otb_bin_path=settings.OTB_BIN_PATH, src=src, dst=dst))

    src = os.path.join(S1_RAW_PATH, 'proc', name, 'calib', 'vh.tiff')
    dst = os.path.join(dst_folder, 'vh.tiff')
    if not os.path.exists(dst):
        run_subprocess(
            '{otb_bin_path}/otbcli_Despeckle -in {src} -out {dst}'.format(
                otb_bin_path=settings.OTB_BIN_PATH, src=src, dst=dst))


def clip(product):
    print("# Clip", product['title'])
    name = '{}.SAFE'.format(product['title'])

    dst_folder = os.path.join(S1_RAW_PATH, 'proc', name, 'clip')
    os.makedirs(dst_folder, exist_ok=True)

    vv_src = os.path.join(S1_RAW_PATH, 'proc', name, 'despeck', 'vv.tiff')
    vv_dst = os.path.join(dst_folder, 'vv.tiff')
    if not os.path.exists(vv_dst):
        run_subprocess(
            '{gdal_bin_path}/gdalwarp -of GTiff -cutline {aoi} -crop_to_cutline {src} {dst}'
            .format(gdal_bin_path=settings.GDAL_BIN_PATH,
                    aoi=AOI_PATH,
                    src=vv_src,
                    dst=vv_dst))

    vh_src = os.path.join(S1_RAW_PATH, 'proc', name, 'despeck', 'vh.tiff')
    vh_dst = os.path.join(dst_folder, 'vh.tiff')
    if not os.path.exists(vh_dst):
        run_subprocess(
            '{gdal_bin_path}/gdalwarp -of GTiff -cutline {aoi} -crop_to_cutline {src} {dst}'
            .format(gdal_bin_path=settings.GDAL_BIN_PATH,
                    aoi=AOI_PATH,
                    src=vh_src,
                    dst=vh_dst))


def concatenate(product):
    print("# Concatenate", product['title'])
    name = '{}.SAFE'.format(product['title'])

    dst_folder = os.path.join(S1_RAW_PATH, 'proc', name, 'concatenate')
    os.makedirs(dst_folder, exist_ok=True)

    vv_src = os.path.join(S1_RAW_PATH, 'proc', name, 'clip', 'vv.tiff')
    vh_src = os.path.join(S1_RAW_PATH, 'proc', name, 'clip', 'vh.tiff')
    dst = os.path.join(dst_folder, 'concatenate.tiff')
    if not os.path.exists(dst):
        run_subprocess(
            '{otb_bin_path}/otbcli_ConcatenateImages -il {vv_src} {vh_src} -out {dst}'
            .format(otb_bin_path=settings.OTB_BIN_PATH,
                    vv_src=vv_src,
                    vh_src=vh_src,
                    dst=dst))


def superimpose(products):
    print("# Superimpose")

    ref_product = products[0]
    ref_name = '{}.SAFE'.format(ref_product['title'])

    inr = os.path.join(S1_RAW_PATH, 'proc', ref_name, 'concatenate', 'concatenate.tiff')
    dst = os.path.join(S1_RAW_PATH, 'proc', ref_name, 'concatenate', 'aligned.tiff')
    if not os.path.exists(dst):
        shutil.copyfile(inr, dst)

    for p in products[1:]:
        name = '{}.SAFE'.format(p['title'])
        inm = os.path.join(S1_RAW_PATH, 'proc', name, 'concatenate', 'concatenate.tiff')
        dst = os.path.join(S1_RAW_PATH, 'proc', name, 'concatenate', 'aligned.tiff')
        if not os.path.exists(dst):
            run_subprocess(
                '{otb_bin_path}/otbcli_Superimpose -inr {inr} -inm {inm} -out {out}'
                .format(otb_bin_path=settings.OTB_BIN_PATH,
                        inr=inr,
                        inm=inm,
                        out=dst))


def median(products, period):
    print("# Generate median composite", period)

    ref_product = products[0]
    ref_name = '{}.SAFE'.format(ref_product['title'])

    ref_path = os.path.join(S1_RAW_PATH, 'proc', ref_name, 'concatenate',
                            'aligned.tiff')

    if not os.path.isdir(os.path.join(S1_RES_PATH, str(period.pk))):
        os.makedirs(os.path.join(S1_RES_PATH, str(period.pk)))

    dst_path = os.path.join(S1_RES_PATH, str(period.pk), 'median.tiff')
    if not os.path.exists(dst_path):
        with rasterio.open(ref_path) as src:
            with rasterio.open(dst_path,
                               'w',
                               driver='GTiff',
                               dtype=src.profile['dtype'],
                               width=src.shape[1],
                               height=src.shape[0],
                               count=src.count,
                               transform=src.profile['transform'],
                               crs=src.profile['crs']) as dst:
                for band in range(1, src.count + 1):
                    for win in sliding_windows(1000, src.shape[1],
                                               src.shape[0]):
                        imgs = []
                        for p in products:
                            name = '{}.SAFE'.format(p['title'])
                            path = os.path.join(S1_RAW_PATH, 'proc', name,
                                                'concatenate',
                                                'aligned.tiff')
                            src = rasterio.open(path)
                            w = src.read(band, window=win)
                            imgs.append(w)

                        wins = np.dstack(imgs)
                        median = np.median(wins, axis=2)
                        dst.write(median, window=win, indexes=band)

    #shutil.rmtree(os.path.join(S1_RAW_PATH, 'proc'))


def generate_vvvh(period):
    print("# Generate VV/VH band", period)
    src = os.path.join(S1_RES_PATH, str(period.pk), 'median.tiff')
    dst = os.path.join(S1_RES_PATH, str(period.pk), 'vv-vh.tiff')
    if not os.path.exists(dst):
        run_subprocess(
            '{otb_bin_path}/otbcli_BandMath -il {src} -out {dst} -exp "im1b1 / im1b2"'
            .format(otb_bin_path=settings.OTB_BIN_PATH, src=src, dst=dst))


def concatenate_results(period):
    print("# Concatenate results", period)
    median = os.path.join(S1_RES_PATH, str(period.pk), 'median.tiff')
    vv_vh = os.path.join(S1_RES_PATH, str(period.pk), 'vv-vh.tiff')
    dst = os.path.join(S1_RES_PATH, str(period.pk), 'concatenate.tiff')
    if not os.path.exists(dst):
        run_subprocess(
            '{otb_bin_path}/otbcli_ConcatenateImages -il {median} {vv_vh} -out {dst}'
            .format(otb_bin_path=settings.OTB_BIN_PATH,
                    median=median,
                    vv_vh=vv_vh,
                    dst=dst))


def clip_result(period):
    print("# Clip result", period)
    src = os.path.join(S1_RES_PATH, str(period.pk), 'concatenate.tiff')
    results_src_dir = os.path.join(settings.BASE_DIR, 'data', 'images',
                                   'results', 'src')
    os.makedirs(results_src_dir, exist_ok=True)
    dst_name = 's1_{}{}_{}{}.tif'.format(period.init_date.year,
                                         period.init_date.month,
                                         period.end_date.year,
                                         period.end_date.month)
    dst = os.path.join(results_src_dir, dst_name)
    if not os.path.exists(dst):
        run_subprocess(
            '{gdal_bin_path}/gdalwarp -of GTiff -cutline {aoi} -crop_to_cutline {src} {dst}'
            .format(gdal_bin_path=settings.GDAL_BIN_PATH,
                    aoi=AOI_PATH,
                    src=src,
                    dst=dst))
