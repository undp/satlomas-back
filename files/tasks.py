from sentinelsat.sentinel import SentinelAPI, read_geojson, geojson_to_wkt
from django_rq import job
import os
from django.conf import settings
from zipfile import ZipFile
import subprocess
from pathlib import Path
import json

# import django_rq; from datetime import date; date_from = date(2019,4,1); date_to = date(2019,4,10);queue = django_rq.get_queue('default', default_timeout=36000);queue.enqueue("files.tasks.download_sentinel2", date_from, date_to);w = django_rq.get_worker(); w.work()

def run_subprocess(cmd):
    print(cmd)
    subprocess.run(cmd, shell=True, check=True)


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
    
    #sen2cor
    return_values = []
    for item in os.listdir(settings.IMAGES_PATH):
        if item.endswith(".SAFE"):
            print("Running sen2cor for {}".format(item))
            folder_name = os.path.abspath(item)
            rv = os.system("sen2cor -f {}".format(folder_name))
            return_values.append(rv)

    # si fallan todas las imagenes de sen2cor, levantar excepcion
    error = all([rv == 0 for rv in return_values])
    if error == False:
        raise ValueError('All sen2cor images failed.')

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
        cmd = "python3 {} -te {} {} {} {} -e 32718 -res 20 -n {} -v -o {} {}".format(
            settings.S2M_PATH, xmin, ymin, xmax, ymax, "name_of_mosaic", os.path.join(settings.IMAGES_PATH,"results"), settings.IMAGES_PATH
        )
        run_subprocess(cmd)
        rv = os.system(cmd)
        # si return value != 0, s2m falló, generar excepcion
        if rv != 0:
            raise ValueError('sen2mosaic failed for {}.'.format(item))

    else:
        print("No GDAL info found on raw folder.")

