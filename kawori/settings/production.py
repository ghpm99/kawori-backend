import os

import sentry_sdk

from kawori.settings.base import *  # noqa: F403, F401

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DNS"),
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    # We recommend adjusting this value in production.
    traces_sample_rate=1.0,
)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("SECRET_KEY")

# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": os.environ.get("NAME"),
        "USER": os.environ.get("USER"),
        "PASSWORD": os.environ.get("PASSWORD"),
        "HOST": os.environ.get("HOST"),
    }
}

CORS_ALLOW_ORIGINS = ["https://www.kawori.site/"]

BASE_URL_FRONTEND = "https://www.kawori.site"

BASE_URL_FRONTEND_FINANCIAL = "https://financeiro.kawori.site"

BASE_URL_FRONTEND_LIST = [BASE_URL_FRONTEND, BASE_URL_FRONTEND_FINANCIAL]

COOKIE_DOMAIN = ".kawori.site"
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
ENVIRONMENT_NAME = "production"
AI_PROMPT_ENVIRONMENT = os.environ.get("AI_PROMPT_ENVIRONMENT", ENVIRONMENT_NAME)


try:
    from kawori.settings.local_settings import *  # noqa: F403, F401
except ImportError:
    pass
