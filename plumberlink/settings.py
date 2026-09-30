"""
PlumberLink — Django settings for the pilot deployment.

Environment variables (all optional for local dev):
    PLUMBERLINK_SECRET_KEY   Django secret key (set a strong one in production)
    PLUMBERLINK_DEBUG        "1" (default) or "0"
    PLUMBERLINK_HOSTS        comma-separated hosts, e.g. "example.com,abc.trycloudflare.com"
    PLUMBERLINK_CSRF_ORIGINS comma-separated origins, e.g. "https://abc.trycloudflare.com"
    PLUMBERLINK_PUBLIC_URL   public base URL used inside generated QR codes
    DATABASE_URL             postgres://... to switch from SQLite to PostgreSQL
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _csv(name: str, default: str = "") -> list[str]:
    return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


SECRET_KEY = os.environ.get("PLUMBERLINK_SECRET_KEY", "dev-only-insecure-key-change-in-production")
DEBUG = os.environ.get("PLUMBERLINK_DEBUG", "1") == "1"

ALLOWED_HOSTS = _csv("PLUMBERLINK_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = _csv("PLUMBERLINK_CSRF_ORIGINS", "")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "plumberlink.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "plumberlink.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

_db_url = os.environ.get("DATABASE_URL", "")
if _db_url.startswith(("postgres://", "postgresql://")):
    # Needs: pip install "psycopg[binary]"
    from urllib.parse import urlparse

    u = urlparse(_db_url)
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": u.path.lstrip("/"),
        "USER": u.username,
        "PASSWORD": u.password,
        "HOST": u.hostname,
        "PORT": u.port or 5432,
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "core" / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Public base URL baked into generated QR codes, e.g. https://xyz.trycloudflare.com
PUBLIC_BASE_URL = os.environ.get("PLUMBERLINK_PUBLIC_URL", "http://localhost:8000").rstrip("/")

LOGIN_URL = "/provider/login/"
LOGIN_REDIRECT_URL = "/provider/"
LOGOUT_REDIRECT_URL = "/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
