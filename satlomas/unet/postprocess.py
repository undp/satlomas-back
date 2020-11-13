import math
import os
import tempfile
from glob import glob

import numpy as np
import rasterio
from django.conf import settings
from tqdm import tqdm

from .utils import grouper, run_command


def coalesce_and_binarize(src_path, threshold=0.5, *, output_dir):
    # Read image
    with rasterio.open(src_path) as src:
        profile = src.profile.copy()
        img = np.dstack(src.read())

    # Build mask
    mask_t = threshold * 255
    mask = img[:, :, 0] >= mask_t
    for b in range(1, img.shape[2]):
        mask = mask | (img[:, :, b] >= mask_t)
    mask = mask.astype(np.uint8)

    # Get class with max probability and apply mask
    max_img = ((np.argmax(img, axis=2) + 1) * mask).astype(np.uint8)

    # Write image
    dst_path = os.path.join(output_dir, os.path.basename(src_path))
    profile.update(count=1, nodata=0)
    with rasterio.open(dst_path, 'w', **profile) as dst:
        dst.write(max_img, 1)


def coalesce_and_binarize_all(threshold=0.75, *, input_dir, output_dir):
    images = glob(os.path.join(input_dir, '*.tif'))
    os.makedirs(output_dir, exist_ok=True)
    # TODO: Use multiprocessing
    for image in tqdm(images):
        coalesce_and_binarize(image,
                              threshold=threshold,
                              output_dir=output_dir)


def gdal_merge(output, files):
    gdal_merge_bin = f'{settings.GDAL_BIN_PATH}/gdal_merge.py'
    cmd = f"{gdal_merge_bin} -n 0 -a_nodata 0 " \
        f"-co TILED=YES " \
        f"-o {output} {' '.join(files)}"
    run_command(cmd)


def merge_all(batch_size=1000, temp_dir=None, *, input_dir, output):
    files = sorted(list(glob(os.path.join(input_dir, '*.tif'))))
    if not files:
        print("No files")

    tmpdir = None
    if not temp_dir:
        tmpdir = tempfile.TemporaryDirectory()
        temp_dir = tmpdir.name

    os.makedirs(temp_dir, exist_ok=True)

    merged_files = []
    total = math.ceil(len(files) / batch_size)
    for i, group in tqdm(enumerate(grouper(files, batch_size)), total=total):
        dst = os.path.join(temp_dir, f"{i}.tif")
        group = [f for f in group if f]
        gdal_merge(dst, group)
        merged_files.append(dst)

    os.makedirs(os.path.dirname(output), exist_ok=True)
    if os.path.exists(output):
        os.unlink(output)

    gdal_merge(output, merged_files)

    if tmpdir:
        tmpdir.cleanup()

    print(f"{output} written")
