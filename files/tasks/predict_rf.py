from django.conf import settings
from django_rq import job

import shutil
import subprocess
import os

RESULTS_DIR = os.path.join(settings.BASE_DIR, 'data', 'images', 'results')
RESULTS_SRC = os.path.join(RESULTS_DIR, 'src')
RESULTS_FEAT = os.path.join(RESULTS_DIR, 'feats')
MODEL_PATH = os.path.join(settings.BASE_DIR, 'files','data','rf_model.yaml')
SRTM_DEM_PATH = os.path.join(settings.BASE_DIR, 'files','data','srtm_dem.tif')


def run_subprocess(cmd):
    print(cmd)
    subprocess.run(cmd, shell=True, check=True)


def superimpose(inm, inr):
    run_subprocess('{otb_bin_path}/otbcli_Superimpose -inr {inr} -inm {inm} -out {out}'.format(
                otb_bin_path=settings.OTB_BIN_PATH,
                inr=os.path.join(RESULTS_SRC, "{}.tif".format(inr)),
                inm=os.path.join(RESULTS_SRC, "{}.tif".format(inm)), 
                out=os.path.join(RESULTS_FEAT, "{}.tif".format(inm))))


def extract_local_stats(name, band):
    run_subprocess('{otb_bin_path}/otbcli_LocalStatisticExtraction -in {input} -channel {band} -radius 3 -out {out}'.format(
                otb_bin_path=settings.OTB_BIN_PATH,
                input=os.path.join(RESULTS_FEAT, "{}.tif".format(name)),
                band=band, 
                out=os.path.join(RESULTS_FEAT, 'local_stats_{}_{}.tif'.format(name, band))))


def extract_haralick(name, band):
    run_subprocess('{otb_bin_path}/otbcli_HaralickTextureExtraction -in {input} -channel {band} -texture simple -parameters.min 0 -parameters.max 0.3 -out {out}'.format(
                otb_bin_path=settings.OTB_BIN_PATH,
                input=os.path.join(RESULTS_FEAT, "{}.tif".format(name)),
                band=band, 
                out=os.path.join(RESULTS_FEAT, 'haralick_{}_{}.tif'.format(name, band))))


def concatenate_images():
    current_dir = os.getcwd()
    os.chdir(RESULTS_FEAT)
    run_subprocess('{otb_bin_path}/otbcli_ConcatenateImages -il $(ls {il}) -out {out}'.format(
            otb_bin_path=settings.OTB_BIN_PATH,
            il=RESULTS_FEAT,
            out=os.path.join(RESULTS_DIR, 'features.tif')))
    os.chdir(current_dir)


def classify_image():
    run_subprocess('{otb_bin_path}/otbcli_ImageClassifier -in {input} -model {model} -out {out}'.format(
            otb_bin_path=settings.OTB_BIN_PATH,
            input=os.path.join(RESULTS_DIR, 'features.tif'),
            model=MODEL_PATH,
            out=os.path.join(RESULTS_DIR, 'cover.tif')))


@job("default", timeout=3600)
def predict_rf(date_from, date_to):
    period = "{}{}_{}{}".format(date_from.year, date_from.month, date_to.year, date_to.month)
    s2_10m = "s2_{}_10m".format(period)
    s2_20m = "s2_{}_20m".format(period)
    s1 = "s1_{}".format(period)
    srtm = "srtm_dem"

    shutil.copyfile(
        os.path.join(RESULTS_SRC, "{}.tif".format(s2_10m)),
        os.path.join(RESULTS_FEAT, "{}.tif".format(s2_10m))
    )
    superimpose(s2_20m, s2_10m)
    superimpose(s1, s2_10m)
    
    shutil.copyfile(
        SRTM_DEM_PATH,
        os.path.join(RESULTS_SRC, "{}.tif".format(srtm))
    )
    superimpose(srtm, s2_10m)

    for b in range(1,9):
        extract_local_stats(s2_10m, b)
        extract_haralick(s2_10m, b)
    
    for b in range(1,7):
        extract_local_stats(s2_20m, b)
        extract_haralick(s2_20m, b)
    
    for b in range(1,4):
        extract_local_stats(s1, b)
        extract_haralick(s1, b)

    extract_local_stats(srtm, 1)
    extract_haralick(srtm, 1)

    concatenate_images()
    classify_image()