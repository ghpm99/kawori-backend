import os
import sentry_sdk
from kawori.settings.base import *


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

sentry_sdk.init(
    dsn=os.environ.get('SENTRY_DNS'),

    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    # We recommend adjusting this value in production.
    traces_sample_rate=1.0
)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY')

# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': os.environ.get('NAME'),
        'USER': os.environ.get('USER'),
        'PASSWORD': os.environ.get('PASSWORD'),
        'HOST': os.environ.get('HOST')
    }
}

BASE_URL = os.environ.get('BASE_URL')
BASE_URL_FRONT = os.environ.get('BASE_URL_FRONT')

ALLOWED_HOSTS = [BASE_URL, BASE_URL_FRONT, '0.0.0.0']
