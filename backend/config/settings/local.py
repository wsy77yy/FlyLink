import os

from .base import *  # noqa: F401,F403


SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'flylink-local-development-only')
DEBUG = True
ALLOWED_HOSTS = ['*']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': Path(os.getenv('SQLITE_PATH', BASE_DIR / 'db.sqlite3')),  # noqa: F405
    }
}

CORS_ALLOW_ALL_ORIGINS = True
CSRF_TRUSTED_ORIGINS = [
    'http://127.0.0.1:8000',
    'http://localhost:8000',
]
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
