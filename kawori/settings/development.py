from dotenv import load_dotenv
import os
from kawori.settings.base import *  # noqa: F403, F401


load_dotenv()

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY')

# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'kawori',
        'USER': 'postgres',
        'PASSWORD': '',
        'HOST': '127.0.0.1',
        'PORT': '',
    }
}

ALLOWED_HOSTS = ['*']

BASE_URL = 'http://localhost:8000'

BASE_URL_WEBHOOK = 'http://localhost:8100'

BASE_URL_FRONTEND = 'http://localhost:3000'

try:
    from kawori.settings.local_settings import *  # noqa: F403, F401
except ImportError:
    pass
