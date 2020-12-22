import os

import eo_sensors
from django.conf import settings

TASKS_DATA_DIR = settings.EO_SENSORS_TASKS_DATA_DIR

APP_DIR = os.path.dirname(eo_sensors.__file__)
APP_DATA_DIR = os.path.join(APP_DIR, 'data')
