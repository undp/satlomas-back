from sentinelsat.sentinel import SentinelAPI, read_geojson, geojson_to_wkt
from django_rq import job
import os
from django.conf import settings
from zipfile import ZipFile
import subprocess
from pathlib import Path
import json

# import django_rq; from datetime import date; date_from = date(2019,4,1); date_to = date(2019,5,1); queue = django_rq.get_queue('default', default_timeout=36000); queue.enqueue("files.tasks.download_sentinel2", date_from, date_to); w = django_rq.get_worker(); w.work()

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

    # s2m
    for item in os.listdir(settings.IMAGES_PATH):
        if item.startswith("S2B_MSIL2A") and item.endswith(".SAFE"):
            print("Run s2m for {}".format(item))
            info = None
            for filename in Path(os.path.join(settings.IMAGES_PATH,item)).rglob("*/IMG_DATA/R20m/*.jp2"):
                print("get info from {}".format(filename))
                info = subprocess.getoutput("gdalinfo -json {}".format(filename))
                break

            if info == None:
                print("No GDAL info found on this folder.")
                continue

            info = json.loads(info)
            print(info)

            print(info["cornerCoordinates"]["upperLeft"])
            print(info["cornerCoordinates"]["lowerRight"])

            xmin = min(info["cornerCoordinates"]["upperLeft"][0], info["cornerCoordinates"]["lowerRight"][0])
            ymin = min(info["cornerCoordinates"]["upperLeft"][1], info["cornerCoordinates"]["lowerRight"][1])
            xmax = max(info["cornerCoordinates"]["upperLeft"][0], info["cornerCoordinates"]["lowerRight"][0])
            ymax = max(info["cornerCoordinates"]["upperLeft"][1], info["cornerCoordinates"]["lowerRight"][1])

            cmd = "python3 {} -te {} {} {} {} -e 32718 -res 20 -n {} -v -o {}".format(
                settings.S2M_PATH, xmin, ymin, xmax, ymax, item, settings.IMAGES_PATH
            )
            print(cmd)
            os.system(cmd)


@job("default", timeout=3600)
def download_sentinel1():
    SCIHUB_URL = 'https://scihub.copernicus.eu/dhus'


    root_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..')
    aoi_path = os.path.join(root_path, 'data', 'aoi_4326.geojson')
    download_path = os.path.join(root_path, 'data', 'images', 's1', '_real')

    api = SentinelAPI(settings.SCIHUB_USER, settings.SCIHUB_PASS,SCIHUB_URL)

    footprint = geojson_to_wkt(read_geojson(aoi_path))
    products = api.query(footprint,
                        date=(settings.DATE_FROM_S1, settings.DATE_UP_TO_S1),
                        platformname='Sentinel-1',
                        producttype='GRD',
                        polarisationmode='VV VH',
                        orbitdirection='ASCENDING')

    for k, p in products.items():
        print((k, p['summary']))

    os.makedirs(download_path, exist_ok=True)

    results = api.download_all(products, directory_path=settings.IMAGES_PATH_S1)
    print(results)
