import os
import shutil
from datetime import date

import dateutil.relativedelta
import django_rq
import numpy as np
import rasterio
from django.conf import settings
from rasterio.windows import Window
from sentinelsat.sentinel import SentinelAPI, geojson_to_wkt, read_geojson

import lomas_changes
from lomas_changes.models import Period, Product
from lomas_changes.predict_rf import predict_rf
from lomas_changes.utils import run_subprocess, sliding_windows, unzip

APPDIR = os.path.dirname(lomas_changes.__file__)

S1_RAW_PATH = os.path.join(settings.BASE_DIR, 'data', 'images', 's1', 'raw')
S1_RES_PATH = os.path.join(settings.BASE_DIR, 'data', 'images', 's1',
                           'results')


def clip_result(period):
    src = os.path.join(S1_RES_PATH, str(period.pk), 'concatenate.tiff')
    RESULTS_SRC = os.path.join(settings.BASE_DIR, 'data', 'images', 'results',
                               'src')
    dst_name = 's1_{}{}_{}{}.tif'.format(period.init_date.year,
                                         period.init_date.month,
                                         period.end_date.year,
                                         period.end_date.month)
    dst = os.path.join(RESULTS_SRC, dst_name)
    aoi_path = os.path.join(APPDIR, 'data', 'extent.geojson')
    run_subprocess(
        '{gdal_bin_path}/gdalwarp -of GTiff -cutline {aoi} -crop_to_cutline {src} {dst}'
        .format(gdal_bin_path=settings.GDAL_BIN_PATH,
                aoi=aoi_path,
                src=src,
                dst=dst))

    period.s1_finished = True
    period.save()
    if period.s2_finished:
        predict_rf(period)


def concatenate_results(period):
    median = os.path.join(S1_RES_PATH, str(period.pk), 'median.tiff')
    vv_vh = os.path.join(S1_RES_PATH, str(period.pk), 'vv-vh.tiff')
    dst = os.path.join(S1_RES_PATH, str(period.pk), 'concatenate.tiff')
    run_subprocess(
        '{otb_bin_path}/otbcli_ConcatenateImages -il {median} {vv_vh} -out {dst}'
        .format(otb_bin_path=settings.OTB_BIN_PATH,
                median=median,
                vv_vh=vv_vh,
                dst=dst))


def generate_vvvh(period):
    src = os.path.join(S1_RES_PATH, str(period.pk), 'median.tiff')
    dst = os.path.join(S1_RES_PATH, str(period.pk), 'vv-vh.tiff')
    run_subprocess(
        '{otb_bin_path}/otbcli_BandMath -il {src} -out {dst} -exp "im1b1 / im1b2"'
        .format(otb_bin_path=settings.OTB_BIN_PATH, src=src, dst=dst))


def median(period):
    reference_path = os.path.join(S1_RAW_PATH, 'proc',
                                  period.products.first().name, 'concatenate',
                                  'concatenate.tiff')
    src = rasterio.open(reference_path)
    if not os.path.isdir(os.path.join(S1_RES_PATH, str(period.pk))):
        os.makedirs(os.path.join(S1_RES_PATH, str(period.pk)))
    with rasterio.open(os.path.join(S1_RES_PATH, str(period.pk),
                                    'median.tiff'),
                       'w',
                       driver='GTiff',
                       dtype=src.profile['dtype'],
                       width=src.shape[1],
                       height=src.shape[0],
                       count=src.count,
                       transform=src.profile['transform'],
                       crs=src.profile['crs']) as dst:
        for band in range(1, src.count + 1):
            for win in sliding_windows(1000, src.shape[1], src.shape[0]):
                imgs = []
                for prod in period.products.all():
                    path = os.path.join(S1_RAW_PATH, 'proc', prod.name,
                                        'concatenate', 'concatenate.tiff')
                    src = rasterio.open(path)
                    w = src.read(band, window=win)
                    imgs.append(w)

                wins = np.dstack(imgs)
                median = np.median(wins, axis=2)
                dst.write(median, window=win, indexes=band)

    shutil.rmtree(os.path.join(S1_RAW_PATH, 'proc'))


def superimpose(period):
    reference = period.products.first()
    inr = os.path.join(S1_RAW_PATH, 'proc', reference.name, 'concatenate',
                       'concatenate.tiff')
    for prod in period.products.all():
        if reference != prod:
            inm = os.path.join(S1_RAW_PATH, 'proc', prod.name, 'concatenate',
                               'concatenate.tiff')
            run_subprocess(
                '{otb_bin_path}/otbcli_Superimpose -inr {inr} -inm {inm} -out {out}'
                .format(otb_bin_path=settings.OTB_BIN_PATH,
                        inr=inr,
                        inm=inm,
                        out=inm))


def manage_results(period):
    superimpose(period)
    median(period)
    generate_vvvh(period)
    concatenate_results(period)
    clip_result(period)


def calibrate(product):
    dst_folder = os.path.join(S1_RAW_PATH, 'proc', product.name, 'calib')
    os.makedirs(dst_folder, exist_ok=True)

    src = os.path.join(S1_RAW_PATH, product.name, 'measurement', '*-vv-*.tiff')
    dst = os.path.join(dst_folder, 'vv.tiff')
    run_subprocess(
        '{otb_bin_path}/otbcli_SARCalibration -in $(ls {src}) -out {dst}'.
        format(otb_bin_path=settings.OTB_BIN_PATH, src=src, dst=dst))

    src = os.path.join(S1_RAW_PATH, product.name, 'measurement', '*-vh-*.tiff')
    dst = os.path.join(dst_folder, 'vh.tiff')
    run_subprocess(
        '{otb_bin_path}/otbcli_SARCalibration -in $(ls {src}) -out {dst}'.
        format(otb_bin_path=settings.OTB_BIN_PATH, src=src, dst=dst))

    shutil.rmtree(os.path.join(S1_RAW_PATH, product.name))

    despeckle(product)


def despeckle(product):
    dst_folder = os.path.join(S1_RAW_PATH, 'proc', product.name, 'despeck')
    os.makedirs(dst_folder, exist_ok=True)

    src = os.path.join(S1_RAW_PATH, 'proc', product.name, 'calib', 'vv.tiff')
    dst = os.path.join(dst_folder, 'vv.tiff')
    run_subprocess(
        '{otb_bin_path}/otbcli_Despeckle -in {src} -out {dst}'.format(
            otb_bin_path=settings.OTB_BIN_PATH, src=src, dst=dst))

    src = os.path.join(S1_RAW_PATH, 'proc', product.name, 'calib', 'vh.tiff')
    dst = os.path.join(dst_folder, 'vh.tiff')
    run_subprocess(
        '{otb_bin_path}/otbcli_Despeckle -in {src} -out {dst}'.format(
            otb_bin_path=settings.OTB_BIN_PATH, src=src, dst=dst))

    shutil.rmtree(os.path.join(S1_RAW_PATH, 'proc', product.name, 'calib'))

    clip(product)


def clip(product):
    dst_folder = os.path.join(S1_RAW_PATH, 'proc', product.name, 'clip')
    os.makedirs(dst_folder, exist_ok=True)
    aoi_path = os.path.join(APPDIR, 'data', 'extent.geojson')

    vv_src = os.path.join(S1_RAW_PATH, 'proc', product.name, 'despeck',
                          'vv.tiff')
    vv_dst = os.path.join(dst_folder, 'vv.tiff')
    run_subprocess(
        '{gdal_bin_path}/gdalwarp -of GTiff -cutline {aoi} -crop_to_cutline {src} {dst}'
        .format(gdal_bin_path=settings.GDAL_BIN_PATH,
                aoi=aoi_path,
                src=vv_src,
                dst=vv_dst))

    vh_src = os.path.join(S1_RAW_PATH, 'proc', product.name, 'despeck',
                          'vh.tiff')
    vh_dst = os.path.join(dst_folder, 'vh.tiff')
    run_subprocess(
        '{gdal_bin_path}/gdalwarp -of GTiff -cutline {aoi} -crop_to_cutline {src} {dst}'
        .format(gdal_bin_path=settings.GDAL_BIN_PATH,
                aoi=aoi_path,
                src=vh_src,
                dst=vh_dst))

    shutil.rmtree(os.path.join(S1_RAW_PATH, 'proc', product.name, 'despeck'))

    concatenate(product)


def concatenate(product):
    dst_folder = os.path.join(S1_RAW_PATH, 'proc', product.name, 'concatenate')
    os.makedirs(dst_folder, exist_ok=True)

    vv_src = os.path.join(S1_RAW_PATH, 'proc', product.name, 'clip', 'vv.tiff')
    vh_src = os.path.join(S1_RAW_PATH, 'proc', product.name, 'clip', 'vh.tiff')
    dst = os.path.join(dst_folder, 'concatenate.tiff')
    run_subprocess(
        '{otb_bin_path}/otbcli_ConcatenateImages -il {vv_src} {vh_src} -out {dst}'
        .format(otb_bin_path=settings.OTB_BIN_PATH,
                vv_src=vv_src,
                vh_src=vh_src,
                dst=dst))

    shutil.rmtree(os.path.join(S1_RAW_PATH, 'proc', product.name, 'clip'))

    product.concatenated = True
    product.save()
    if not Product.objects.filter(period=product.period,
                                  concatenated=False).exists():
        manage_results(product.period)


def download_scenes(period):
    init_date = period.init_date
    end_date = period.end_date

    aoi_path = os.path.join(settings.BASE_DIR, 'files', 'aoi_4326.geojson')

    api = SentinelAPI(settings.SCIHUB_USER, settings.SCIHUB_PASS,
                      settings.SCIHUB_URL)

    footprint = geojson_to_wkt(read_geojson(aoi_path))
    products = api.query(footprint,
                         date=(init_date, end_date),
                         platformname='Sentinel-1',
                         producttype='GRD',
                         polarisationmode='VV VH',
                         orbitdirection='ASCENDING')

    for k, p in products.items():
        print((k, p['summary']))

    os.makedirs(S1_RAW_PATH, exist_ok=True)

    results = api.download_all(products, directory_path=S1_RAW_PATH)
    if len(results[0].items()) > 0:
        for k, p in results[0].items():
            prod = Product.objects.create(code=p['id'],
                                          sensor_type=Product.SENTINEL1,
                                          datetime=p['date'],
                                          name='{}.SAFE'.format(p['title']),
                                          period=period)
            unzip(p['path'])
            calibrate(prod)
