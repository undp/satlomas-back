import os
import zipfile
import subprocess


def run_subprocess(cmd):
    print(cmd)
    subprocess.run(cmd, shell=True, check=True)


def unzip(zip_name, extract_folder=None, delete_zip=True):
    if extract_folder is None:
        extract_folder = os.path.dirname(zip_name)
    resultzip = zipfile.ZipFile(zip_name)
    resultzip.extractall(extract_folder)
    resultzip.close()
    if delete_zip:
        os.remove(zip_name)


def sliding_windows(size, width, height):
    """Slide a window of +size+ pixels"""
    for i in range(0, height, size):
        for j in range(0, width, size):
            yield Window(j, i, min(width - j, size), min(height - i, size))
