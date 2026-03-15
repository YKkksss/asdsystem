import os
from pathlib import Path

from dotenv import load_dotenv

from config.logging_config import build_logging_config, resolve_log_dir

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_list(name: str, default: str = "") -> list[str]:
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-secret-key-for-asd-system-2026")
DEBUG = get_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = get_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost,backend")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "django_filters",
    "apps.audit",
    "apps.common",
    "apps.organizations",
    "apps.accounts",
    "apps.archives",
    "apps.borrowing",
    "apps.reports",
    "apps.destruction",
    "apps.digitization",
    "apps.notifications",
    "apps.system",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DB_ENGINE = os.getenv("DB_ENGINE", "sqlite").strip().lower()

if DB_ENGINE == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("DB_NAME", "lanchang_archive"),
            "HOST": os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DB_PORT", "3306"),
            "USER": os.getenv("DB_USER", "archive"),
            "PASSWORD": os.getenv("DB_PASSWORD", "archive123456"),
            "OPTIONS": {
                "charset": "utf8mb4",
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / os.getenv("DB_NAME", "db.sqlite3"),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.SystemUser"

REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_DB = os.getenv("REDIS_DB", "0")
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "asd-system-cache",
    }
}

if get_bool("DJANGO_CORS_ALLOW_ALL", False):
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOWED_ORIGINS = get_list("DJANGO_CORS_ALLOWED_ORIGINS")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
    ),
    "EXCEPTION_HANDLER": "apps.common.exceptions.custom_exception_handler",
}

SIMPLE_JWT = {
    "AUTH_HEADER_TYPES": ("Bearer",),
}

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/1")
CELERY_TASK_ALWAYS_EAGER = get_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_TIME_LIMIT = 300
CELERY_TASK_SOFT_TIME_LIMIT = 240
CELERY_BEAT_SCHEDULE = {
    "dispatch-due-borrow-reminders": {
        "task": "borrowing.dispatch_due_borrow_reminders",
        "schedule": 60 * 60,
    }
}

ARCHIVE_UPLOAD_MAX_SIZE_MB = int(os.getenv("ARCHIVE_UPLOAD_MAX_SIZE_MB", "50"))
ARCHIVE_FILE_PREVIEW_TICKET_MINUTES = int(os.getenv("ARCHIVE_FILE_PREVIEW_TICKET_MINUTES", "10"))
ARCHIVE_FILE_DOWNLOAD_TICKET_MINUTES = int(os.getenv("ARCHIVE_FILE_DOWNLOAD_TICKET_MINUTES", "5"))
BORROW_REMINDER_BEFORE_DUE_DAYS = int(os.getenv("BORROW_REMINDER_BEFORE_DUE_DAYS", "3"))
BORROW_REMINDER_ESCALATE_DAYS = int(os.getenv("BORROW_REMINDER_ESCALATE_DAYS", "3"))

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = get_bool("EMAIL_USE_TLS", False)
EMAIL_USE_SSL = get_bool("EMAIL_USE_SSL", False)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@asd-system.local")
BACKEND_LOG_LEVEL = os.getenv("BACKEND_LOG_LEVEL", "INFO").strip().upper()
BACKEND_LOG_DIR = resolve_log_dir(BASE_DIR, os.getenv("BACKEND_LOG_DIR"))
BACKEND_LOG_ROTATION_WHEN = os.getenv("BACKEND_LOG_ROTATION_WHEN", "midnight").strip() or "midnight"
BACKEND_LOG_ROTATION_INTERVAL = int(os.getenv("BACKEND_LOG_ROTATION_INTERVAL", "1"))
BACKEND_LOG_BACKUP_COUNT = int(os.getenv("BACKEND_LOG_BACKUP_COUNT", "14"))
SYSTEM_STORAGE_WARNING_PERCENT = float(os.getenv("SYSTEM_STORAGE_WARNING_PERCENT", "85"))
SYSTEM_STORAGE_CRITICAL_PERCENT = float(os.getenv("SYSTEM_STORAGE_CRITICAL_PERCENT", "95"))

LOGGING = build_logging_config(
    level=BACKEND_LOG_LEVEL,
    log_dir=BACKEND_LOG_DIR,
    rotation_when=BACKEND_LOG_ROTATION_WHEN,
    rotation_interval=BACKEND_LOG_ROTATION_INTERVAL,
    backup_count=BACKEND_LOG_BACKUP_COUNT,
)
