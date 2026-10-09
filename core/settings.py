import os, secrets
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get('FLYLINK_DATA', str(BASE_DIR / 'data')))
DATA.mkdir(parents=True, exist_ok=True)
secret = DATA / '.secret'
if not secret.exists(): secret.write_text(secrets.token_urlsafe(64), encoding='utf-8')
SECRET_KEY = secret.read_text(encoding='utf-8')
DEBUG = False
ALLOWED_HOSTS = os.environ.get('FLYLINK_HOSTS', '127.0.0.1,localhost,testserver').split(',')
INSTALLED_APPS = ['django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','core']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware']
DATABASES = {'default': {'ENGINE':'django.db.backends.sqlite3','NAME':DATA/'flylink.sqlite3','OPTIONS':{'timeout':30}}}
ROOT_URLCONF = 'core.urls'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
TIME_ZONE = 'Asia/Shanghai'
USE_TZ = True
LANGUAGE_CODE = 'zh-hans'
MEDIA_ROOT = DATA/'media'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 28800
SESSION_COOKIE_SECURE = os.environ.get('FLYLINK_HTTPS') == '1'
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
CSRF_TRUSTED_ORIGINS = [x for x in os.environ.get('FLYLINK_ORIGINS','').split(',') if x]
DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
TEMPLATES = []

SESSION_COOKIE_NAME='flylink_desktop_session'
CSRF_COOKIE_NAME='flylink_desktop_csrf'
