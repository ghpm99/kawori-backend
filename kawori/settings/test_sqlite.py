from pathlib import Path

from kawori.settings.base import *  # noqa: F403, F401

DEBUG = False
SECRET_KEY = "sqlite-test-secret-key"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(Path(BASE_DIR) / "test_db.sqlite3"),  # noqa: F405
    }
}

ALLOWED_HOSTS = ["*"]

BASE_URL = "http://localhost:8000"
BASE_URL_WEBHOOK = "http://localhost:8100"
BASE_URL_FRONTEND = "http://localhost:3000"
BASE_URL_FRONTEND_FINANCIAL = "http://localhost:5173"
BASE_URL_FRONTEND_LIST = [BASE_URL_FRONTEND, BASE_URL_FRONTEND_FINANCIAL]

CSRF_TRUSTED_ORIGINS = [BASE_URL_FRONTEND, BASE_URL_FRONTEND_FINANCIAL]
CORS_ALLOW_ORIGINS = [BASE_URL_FRONTEND, BASE_URL_FRONTEND_FINANCIAL]
COOKIE_DOMAIN = "localhost"

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

ENV_PUSHER_APP_ID = "1"
ENV_PUSHER_KEY = "test"
ENV_PUSHER_SECRET = "test"
ENV_PUSHER_CLUSTER = "us2"


class DisableMigrations(dict):
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()
