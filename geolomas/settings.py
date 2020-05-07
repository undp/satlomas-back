"""
Django settings for geolomas project.

Generated by 'django-admin startproject' using Django 2.2.6.

For more information on this file, see
https://docs.djangoproject.com/en/2.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.2/ref/settings/
"""

import os
from datetime import date

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = int(os.getenv('DEBUG', 1)) > 0


def get_allowed_hosts():
    """
    Get allowed hosts from .env file

    If DEBUG = True and ALLOWED_HOSTS is empty or null,
    default to ['.dymaxionlabs.com']

    """
    hosts = [s for s in os.getenv('ALLOWED_HOSTS', '').split(',') if s]
    if not DEBUG and not hosts:
        hosts = ['.dymaxionlabs.com']
    return hosts


ALLOWED_HOSTS = get_allowed_hosts()

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.sites',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    'django_extensions',
    'auditlog',
    'rest_framework',
    'rest_framework_gis',
    'rest_framework.authtoken',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'rest_auth',
    'drf_yasg',
    'corsheaders',
    'jsoneditor',
    'django_rq',
    'leaflet',
    'stations.apps.StationsConfig',
    'lomas_changes.apps.LomasChangesConfig',
    'vi_lomas_changes.apps.VILomasChangesConfig',
    'scopes.apps.ScopesConfig',
    'alerts.apps.AlertsConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'geolomas.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
            'libraries': {
                'global_settings': 'geolomas.templatetags.global_settings',
            }
        },
    },  
]

WSGI_APPLICATION = 'geolomas.wsgi.application'

# Allow all domains
CORS_ORIGIN_ALLOW_ALL = True

# Database
# https://docs.djangoproject.com/en/2.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT'),
    }
}

# Password validation
# https://docs.djangoproject.com/en/2.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME':
        'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME':
        'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME':
        'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME':
        'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/2.2/topics/i18n/

LANGUAGE_CODE = os.getenv('LANGUAGE_CODE', 'en-us')

TIME_ZONE = os.getenv('TIME_ZONE', 'UTC')

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.2/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static/')
#STATICFILES_DIRS = [os.path.join(BASE_DIR, 'templates', 'static')]

SITE_ID = 1

RQ_QUEUES = {
    'default': {
        'URL': os.getenv('RQ_REDIS_URL', 'redis://localhost:6379/0'),
        'DEFAULT_TIMEOUT': os.getenv('RQ_TIMEOUT', 360),
    }
}

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': ('rest_framework.renderers.JSONRenderer', ),
    'DEFAULT_AUTHENTICATION_CLASSES':
    ('geolomas.authentication.TokenAuthentication', ),
    'DEFAULT_PERMISSION_CLASSES':
    ('rest_framework.permissions.IsAuthenticated', )
}

RQ_SHOW_ADMIN_LINK = True

MEDIA_ROOT = os.path.join(BASE_DIR, 'media/')
MEDIA_URL = '/media/'

JSON_EDITOR_JS = 'https://cdnjs.cloudflare.com/ajax/libs/jsoneditor/4.2.1/jsoneditor.js'
JSON_EDITOR_CSS = 'https://cdnjs.cloudflare.com/ajax/libs/jsoneditor/4.2.1/jsoneditor.css'

CONFIG_DIR = os.path.join(BASE_DIR, 'config')
DATA_DIR = os.path.join(BASE_DIR, 'data')
IMAGES_PATH = os.path.join(DATA_DIR, 'images', 's2')
IMAGES_PATH_S1 = os.path.join(DATA_DIR, 'images', 's1', 'raw')

SCIHUB_URL = os.getenv('SCIHUB_URL', 'https://scihub.copernicus.eu/dhus')
SCIHUB_USER = os.getenv('SCIHUB_USER')
SCIHUB_PASS = os.getenv('SCIHUB_PASS')

# Sen2mosaic
S2M_CLI_PATH = os.getenv('S2M_CLI_PATH')

# Number of cores to use for multi processing S1 images
S1_PROC_NUM_JOBS = int(os.getenv("S1_PROC_NUM_JOBS", 3))

# OTB
OTB_BIN_PATH = os.getenv('OTB_BIN_PATH')
GDAL_BIN_PATH = os.getenv('GDAL_BIN_PATH')

# MODIS
MODIS_USER = os.getenv('MODIS_USER')
MODIS_PASS = os.getenv('MODIS_PASS')

# shellplus notebook config
NOTEBOOK_ARGUMENTS = ['--ip', '0.0.0.0', '--port', '8888']

# For images and other uploaded files
# In production, add this to your .env:
#   DEFAULT_FILE_STORAGE = 'storages.backends.gcloud.GoogleCloudStorage'
DEFAULT_FILE_STORAGE = os.getenv(
    'DEFAULT_FILE_STORAGE', 'django.core.files.storage.FileSystemStorage')

CACHES = {
    'default': {
        'BACKEND': 'redis_cache.RedisCache',
        'LOCATION': os.getenv('REDIS_CACHE_URL', 'redis://localhost:6379/1'),
    }
}

TILE_SERVER_URL = os.getenv('TILE_SERVER_URL',
                            'http://localhost:8000/media/tiles/')

REST_AUTH_SERIALIZERS = {
    'PASSWORD_RESET_SERIALIZER': 'geolomas.serializers.PasswordResetSerializer'
}

CONTACT_EMAIL = 'contact@dymaxionlabs.com'
COMPANY_NAME = 'Dymaxion Labs'
LIST_ADDRESS_HTML = 'Maipú 812 10E, Ciudad de Buenos Aires, Argentina (C1006ACL)'

WEBCLIENT_URL = os.getenv('WEBCLIENT_URL')
