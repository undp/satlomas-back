from sentinelsat.sentinel import SentinelAPI, read_geojson, geojson_to_wkt
from django_rq import job
import os
from django.conf import settings
from zipfile import ZipFile
import subprocess
from pathlib import Path
import json

# import django_rq; from datetime import date; date_from = date(2019,4,1); date_to = date(2019,5,1); queue = django_rq.get_queue('default', default_timeout=36000); queue.enqueue("files.tasks.download_sentinel2", date_from, date_to); w = django_rq.get_worker(); w.work()

def run_subprocess(cmd):
    print(cmd)
    subprocess.run(cmd, shell=True, check=True)


def generate_vegetation_indexes(mosaic_name):

    nir = os.path.join(settings.IMAGES_PATH,'results','{}_R10m_NIR.vrt'.format(mosaic_name))
    rgb = os.path.join(settings.IMAGES_PATH,'results','{}_R10m_RGB.vrt'.format(mosaic_name))

    #ndiv
    dst = os.path.join(settings.IMAGES_PATH,'results','R10m_NDIV.tif')
    exp = '(im1b1 - im2b1) / (im1b1 + im2b1)'
    run_subprocess('{otb_bin_path}/otbcli_BandMath -il {nir} {rgb} -out {dst} -exp "{exp}"'.format(
                        otb_bin_path=settings.OTB_BIN_PATH,
                        nir=nir, rgb=rgb,
                        dst=dst, exp=exp))
    
    #ndwi
    dst = os.path.join(settings.IMAGES_PATH,'results','R10m_NDWI.tif')
    exp = '(im1b1 - im2b2) / (im1b1 + im2b2)'
    run_subprocess('{otb_bin_path}/otbcli_BandMath -il {nir} {rgb} -out {dst} -exp "{exp}"'.format(
                        otb_bin_path=settings.OTB_BIN_PATH,
                        nir=nir, rgb=rgb,
                        dst=dst, exp=exp))
    
    #evi
    dst = os.path.join(settings.IMAGES_PATH,'results','R10m_EVI.tif')
    exp = '(2.5 * ((im1b1 - im2b1) / (im1b1 + 6 * im2b1 - 7.5 * im2b3 + 1)))'
    run_subprocess('{otb_bin_path}/otbcli_BandMath -il {nir} {rgb} -out {dst} -exp "{exp}"'.format(
                        otb_bin_path=settings.OTB_BIN_PATH,
                        nir=nir, rgb=rgb,
                        dst=dst, exp=exp))

    #savi
    dst = os.path.join(settings.IMAGES_PATH,'results','R10m_SAVI.tif')
    exp = '((im1b1 - im2b1) * 1.5 / (im1b1 + im2b1 + 0.5))'
    run_subprocess('{otb_bin_path}/otbcli_BandMath -il {nir} {rgb} -out {dst} -exp "{exp}"'.format(
                        otb_bin_path=settings.OTB_BIN_PATH,
                        nir=nir, rgb=rgb,
                        dst=dst, exp=exp))


def concatenate_results(mosaic_name, date_from, date_to):
    tif_10m = 's2_{}{}_{}{}_10m.tif'.format(date_from.year,date_from.month,date_to.year,date_to.month)
    tif_20m = 's2_{}{}_{}{}_20m.tif'.format(date_from.year,date_from.month,date_to.year,date_to.month)

    R10m_B02 = os.path.join(settings.IMAGES_PATH,'results','{}_R10m_B02.tif'.format(mosaic_name))
    R10m_B03 = os.path.join(settings.IMAGES_PATH,'results','{}_R10m_B03.tif'.format(mosaic_name))
    R10m_B04 = os.path.join(settings.IMAGES_PATH,'results','{}_R10m_B04.tif'.format(mosaic_name))
    R10m_B08 = os.path.join(settings.IMAGES_PATH,'results','{}_R10m_B08.tif'.format(mosaic_name))
    R10m_NDIV = os.path.join(settings.IMAGES_PATH,'results','R10m_NDIV.tif')
    R10m_NDIV = os.path.join(settings.IMAGES_PATH,'results','R10m_NDWI.tif')
    R10m_EVI = os.path.join(settings.IMAGES_PATH,'results','R10m_EVI.tif')
    R10m_SAVI = os.path.join(settings.IMAGES_PATH,'results','R10m_SAVI.tif')
    src = ' '.join([R10m_B02,R10m_B03,R10m_B04,R10m_B08,R10m_NDIV,R10m_NDIV,R10m_EVI,R10m_SAVI])
    run_subprocess('{otb_bin_path}/otbcli_ConcatenateImages -il {src} -out {dst}'.format(
            otb_bin_path=settings.OTB_BIN_PATH,
            src=src,
            dst=os.path.join(settings.IMAGES_PATH,'results',tif_10m)))
    
    R20m_B05 = os.path.join(settings.IMAGES_PATH,'results','{}_R20m_B05.tif'.format(mosaic_name))
    R20m_B06 = os.path.join(settings.IMAGES_PATH,'results','{}_R20m_B06.tif'.format(mosaic_name))
    R20m_B07 = os.path.join(settings.IMAGES_PATH,'results','{}_R20m_B07.tif'.format(mosaic_name))
    R20m_B8A = os.path.join(settings.IMAGES_PATH,'results','{}_R20m_B8A.tif'.format(mosaic_name))
    R20m_B11 = os.path.join(settings.IMAGES_PATH,'results','{}_R20m_B11.tif'.format(mosaic_name))
    R20m_B12 = os.path.join(settings.IMAGES_PATH,'results','{}_R20m_B12.tif'.format(mosaic_name))
    src = ' '.join([R20m_B05,R20m_B06,R20m_B07,R20m_B8A,R20m_B11,R20m_B12])
    run_subprocess('{otb_bin_path}/otbcli_ConcatenateImages -il {src} -out {dst}'.format(
            otb_bin_path=settings.OTB_BIN_PATH,
            src=src,
            dst=os.path.join(settings.IMAGES_PATH,'results',tif_20m)))


def clip_results(date_from, date_to):
    tif_10m = 's2_{}{}_{}{}_10m.tif'.format(date_from.year,date_from.month,date_to.year,date_to.month)
    tif_20m = 's2_{}{}_{}{}_20m.tif'.format(date_from.year,date_from.month,date_to.year,date_to.month)

    srcs = [tif_10m, tif_20m]
    aoi_path = os.path.join(settings.BASE_DIR, 'files', 'aoi_4326.geojson')

    for src in srcs:
        run_subprocess('{gdal_bin_path}/gdalwarp -of GTiff -cutline {aoi} -crop_to_cutline {src} {dst}'.format(
                gdal_bin_path=settings.GDAL_BIN_PATH,
                aoi=aoi_path,
                src=os.path.join(settings.IMAGES_PATH,'results',src),
                dst=os.path.join(settings.IMAGES_PATH,'final',src)))




@job("default", timeout=3600)
def download_sentinel2(date_from, date_to):
    
    # connect to the API
    api = SentinelAPI(settings.SCIHUB_USER,settings.SCIHUB_PASS, settings.SCIHUB_URL)

    # search by polygon, time, and Hub query keywords
    footprint = geojson_to_wkt(read_geojson(os.path.join(settings.BASE_DIR, 'files', 'aoi_4326.geojson')))

    products = api.query(footprint,       
                        date = (date_from, date_to),
                        platformname = 'Sentinel-2',
                        cloudcoverpercentage = (0, 100))

    # me quedo solo con los productos de nivel 1 que son los que usa sen2cor
    l2 = []
    for p in products:
        if 'MSIL2A' in products[p]['title']:
            l2.append(p)
    # remuevo productos L2
    for p in l2:
        products.pop(p)
    # productos a descargar
    for p in products:
        print(products[p]['title'])
    
    #download all results from the search
    api.download_all(products, directory_path=settings.IMAGES_PATH)

    #unzip
    os.chdir(settings.IMAGES_PATH)
    for item in os.listdir(settings.IMAGES_PATH):
        if item.endswith(".zip"):
            print("unzip {}".format(item))
            file_name = os.path.abspath(item)
            zip_ref = ZipFile(file_name)
            zip_ref.extractall(settings.IMAGES_PATH)
            zip_ref.close() 
    
    # # # sen2cor
    for item in os.listdir(settings.IMAGES_PATH):
        if item.endswith(".SAFE"):
            print("Running sen2cor for {}".format(item))
            folder_name = os.path.abspath(item)
            os.system("sen2cor -f {}".format(folder_name))

    # obtain necesary gdal info
    gdal_info = False
    for item in os.listdir(settings.IMAGES_PATH):
        if item.startswith("S2B_MSIL2A") and item.endswith(".SAFE"):
            info = None
            for filename in Path(os.path.join(settings.IMAGES_PATH,item)).rglob("*/IMG_DATA/R20m/*.jp2"):
                print("get info from {}".format(filename))
                info = subprocess.getoutput("gdalinfo -json {}".format(filename))
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

                xmin = min(info["cornerCoordinates"]["upperLeft"][0], info["cornerCoordinates"]["lowerRight"][0])
                ymin = min(info["cornerCoordinates"]["upperLeft"][1], info["cornerCoordinates"]["lowerRight"][1])
                xmax = max(info["cornerCoordinates"]["upperLeft"][0], info["cornerCoordinates"]["lowerRight"][0])
                ymax = max(info["cornerCoordinates"]["upperLeft"][1], info["cornerCoordinates"]["lowerRight"][1])
                break

    #s2m
    if gdal_info:
        mosaic_name = '{}{}_{}{}_mosaic.tif'.format(date_from.year,date_from.month,date_to.year,date_to.month)
        cmd = "python3 {} -te {} {} {} {} -e 32718 -res 20 -n {} -v -o {} {}".format(
            settings.S2M_PATH, xmin, ymin, xmax, ymax, mosaic_name, os.path.join(settings.IMAGES_PATH,"results"), settings.IMAGES_PATH
        )
        run_subprocess(cmd)

        cmd = "python3 {} -te {} {} {} {} -e 32718 -res 10 -n {} -v -o {} {}".format(
            settings.S2M_PATH, xmin, ymin, xmax, ymax, mosaic_name, os.path.join(settings.IMAGES_PATH,"results"), settings.IMAGES_PATH
        )
        run_subprocess(cmd)

        #delete useless products
        products_delete = os.path.join(settings.IMAGES_PATH,"*.SAFE")
        cmd = "rm -rf {}".format(products_delete)
        run_subprocess(cmd)

        generate_vegetation_indexes(mosaic_name)
        concatenate_results(mosaic_name, date_from, date_to)
        clip_results(date_from, date_to)
    else:
        print("No GDAL info found on raw folder.")

