import logging
import math
import os
import sys
import tempfile
from glob import glob

import numpy as np
import rasterio
import rasterio.mask
import rasterio.merge
import rasterio.windows
import scipy.signal
from django.conf import settings
from rasterio.transform import Affine
from rasterio.windows import Window
from rtree import index
from shapely.geometry import box
from tqdm import tqdm

from .utils import grouper, run_command

logger = logging.getLogger(__name__)
out_handler = logging.StreamHandler(sys.stdout)
out_handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
out_handler.setLevel(logging.INFO)
logger.addHandler(out_handler)
logger.setLevel(logging.INFO)


def spline_window(window_size, power=2):
    """
    Squared spline (power=2) window function:
    https://www.wolframalpha.com/input/?i=y%3Dx**2,+y%3D-(x-2)**2+%2B2,+y%3D(x-4)**2,+from+y+%3D+0+to+2
    """
    intersection = int(window_size / 4)
    wind_outer = (abs(2 * (scipy.signal.triang(window_size)))**power) / 2
    wind_outer[intersection:-intersection] = 0

    wind_inner = 1 - (abs(2 *
                          (scipy.signal.triang(window_size) - 1))**power) / 2
    wind_inner[:intersection] = 0
    wind_inner[-intersection:] = 0

    wind = wind_inner + wind_outer
    wind = wind / np.average(wind)
    return wind


def window_2D(size, power=2, n_channels=1):
    wind = spline_window(size, power)
    wind = np.expand_dims(wind, 0)
    wind = (wind * wind.transpose()) / 4
    wind = np.expand_dims(wind, axis=0)
    return np.repeat(wind, n_channels, axis=0).reshape(n_channels, size, size)


def generate_spline_window_chips(*, image_paths, output_dir):
    """Interpolates all images using a squared spline window"""
    if not image_paths:
        return []

    first_image = image_paths[0]
    with rasterio.open(first_image) as src:
        chip_size = src.width
        n_channels = src.count
        assert (src.width == src.height)

    spline_window = window_2D(size=chip_size, power=2, n_channels=n_channels)

    res = []
    for img_path in tqdm(image_paths):
        with rasterio.open(img_path) as src:
            profile = src.profile.copy()
            img = src.read()

        img = (img * spline_window).astype(np.uint8)

        out_path = os.path.join(output_dir, os.path.basename(img_path))
        os.makedirs(output_dir, exist_ok=True)
        res.append(out_path)
        with rasterio.open(out_path, 'w', **profile) as dst:
            for i in range(img.shape[0]):
                dst.write(img[i, :, :], i + 1)

    return res


# Based on 'max' method from https://github.com/mapbox/rasterio/blob/master/rasterio/merge.py
def mean_merge_method(old_data,
                      new_data,
                      old_nodata,
                      new_nodata,
                      index=None,
                      roff=None,
                      coff=None):
    mask = np.logical_and(~old_nodata, ~new_nodata)
    old_data[mask] = np.mean([old_data[mask], new_data[mask]], axis=0)

    mask = np.logical_and(old_nodata, ~new_nodata)
    old_data[mask] = new_data[mask]


def build_bounds_index(image_files):
    """Returns bounds of merged images and builds an R-Tree index"""
    idx = index.Index()
    xs = []
    ys = []
    for i, img_path in tqdm(list(enumerate(image_files))):
        with rasterio.open(img_path) as src:
            left, bottom, right, top = src.bounds
        xs.extend([left, right])
        ys.extend([bottom, top])
        idx.insert(i, (left, bottom, right, top))
    dst_w, dst_s, dst_e, dst_n = min(xs), min(ys), max(xs), max(ys)
    return idx, (dst_w, dst_s, dst_e, dst_n)


def sliding_windows(size, whole=False, step_size=None, *, width, height):
    """Slide a window of +size+ by moving it +step_size+ pixels"""
    if not step_size:
        step_size = size
    w, h = (size, size)
    sw, sh = (step_size, step_size)
    end_i = height - h if whole else height
    end_j = width - w if whole else width
    for pos_i, i in enumerate(range(0, end_i, sh)):
        for pos_j, j in enumerate(range(0, end_j, sw)):
            real_w = w if whole else min(w, abs(width - j))
            real_h = h if whole else min(h, abs(height - i))
            yield rasterio.windows.Window(j, i, real_w, real_h), (pos_i, pos_j)


def merge_chips(images_files, *, win_bounds):
    """Merge by taking mean between overlapping images"""
    datasets = [rasterio.open(p) for p in images_files]
    img, _ = rasterio.merge.merge(datasets,
                                  bounds=win_bounds,
                                  method=mean_merge_method)
    for ds in datasets:
        ds.close()
    return img


def smooth_stitch(*, input_dir, output_dir):
    """
    Takes input directory of overlapping chips, and generates a new directory
    of non-overlapping chips with smooth edges.
    """
    image_paths = glob(os.path.join(input_dir, '*.tif'))
    if not image_paths:
        raise RuntimeError("%s does not contain any .tif file" % (input_dir))

    # Get the profile and affine of some image as template for output image
    first_image = image_paths[0]
    with rasterio.open(first_image) as src:
        profile = src.profile.copy()
        src_res = src.res
        chip_size = src.width
        assert (src.width == src.height)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_image_paths = generate_spline_window_chips(image_paths=image_paths,
                                                       output_dir=tmpdir)

        # Get bounds from all images and build R-Tree index
        idx, (dst_w, dst_s, dst_e, dst_n) = build_bounds_index(tmp_image_paths)

        # Get affine transform for complete bounds
        logger.info("Output bounds: %r", (dst_w, dst_s, dst_e, dst_n))
        output_transform = Affine.translation(dst_w, dst_n)
        logger.info("Output transform, before scaling: %r", output_transform)

        output_transform *= Affine.scale(src_res[0], -src_res[1])
        logger.info("Output transform, after scaling: %r", output_transform)

        # Compute output array shape. We guarantee it will cover the output
        # bounds completely. We need this to build windows list later.
        output_width = int(math.ceil((dst_e - dst_w) / src_res[0]))
        output_height = int(math.ceil((dst_n - dst_s) / src_res[1]))

        # Set width and height for output chips, and other attributes
        profile.update(width=chip_size, height=chip_size, tiled=True)

        windows = list(
            sliding_windows(chip_size,
                            width=output_width,
                            height=output_height))
        logger.info("Num. windows: %d", len(windows))

        for win, (i, j) in tqdm(windows):
            # Get window affine transform and bounds
            win_transform = rasterio.windows.transform(win, output_transform)
            win_bounds = rasterio.windows.bounds(win, output_transform)

            # Get chips that intersect with window
            intersect_chip_paths = [
                tmp_image_paths[i] for i in idx.intersection(win_bounds)
            ]

            if intersect_chip_paths:
                # Merge them with median method
                img = merge_chips(intersect_chip_paths, win_bounds=win_bounds)

                # Write output chip
                profile.update(transform=win_transform)
                output_path = os.path.join(output_dir, f'{i}_{j}.tif')

                os.makedirs(output_dir, exist_ok=True)
                with rasterio.open(output_path, 'w', **profile) as dst:
                    for i in range(img.shape[0]):
                        dst.write(img[i, :, :], i + 1)


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
    profile.update(count=1, nodata=0, dtype=np.uint8)
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
