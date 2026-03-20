import os

from kawori.settings.base import *  # noqa: F403, F401

DEBUG = False
SECRET_KEY = os.environ.get("SECRET_KEY", "ci-test-secret-key")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": os.environ.get("POSTGRES_DB", "kawori"),
        "USER": os.environ.get("POSTGRES_USER", "postgres"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "postgres"),
        "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "TEST": {"NAME": os.environ.get("POSTGRES_TEST_DB", "test_kawori")},
    }
}

ALLOWED_HOSTS = ["*"]

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
BASE_URL_WEBHOOK = os.environ.get("BASE_URL_WEBHOOK", "http://localhost:8100")
BASE_URL_FRONTEND = os.environ.get("BASE_URL_FRONTEND", "http://localhost:3000")
BASE_URL_FRONTEND_FINANCIAL = os.environ.get(
    "BASE_URL_FRONTEND_FINANCIAL", "http://localhost:5173"
)
BASE_URL_FRONTEND_LIST = [BASE_URL_FRONTEND, BASE_URL_FRONTEND_FINANCIAL]

CSRF_TRUSTED_ORIGINS = [BASE_URL_FRONTEND, BASE_URL_FRONTEND_FINANCIAL]
CORS_ALLOW_ORIGINS = [BASE_URL_FRONTEND, BASE_URL_FRONTEND_FINANCIAL]
COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN", "localhost")

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

ENV_PUSHER_APP_ID = os.environ.get("ENV_PUSHER_APP_ID", "1")
ENV_PUSHER_KEY = os.environ.get("ENV_PUSHER_KEY", "test")
ENV_PUSHER_SECRET = os.environ.get("ENV_PUSHER_SECRET", "test")
ENV_PUSHER_CLUSTER = os.environ.get("ENV_PUSHER_CLUSTER", "us2")

CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_HTTPONLY = False
