import base64
import os

import dj_database_url

SECRET_KEY = "test-secret-key-not-for-production"

DEBUG = False

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.sites",
    "integrations",
    "tests.testapp",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]

ROOT_URLCONF = "tests.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
    },
]

DATABASES = {
    "default": dj_database_url.config(default="sqlite://:memory:"),
}

SITE_ID = 1

USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Ephemeral per-run key; individual tests override this with their own
# fixed keys via @override_settings where deterministic behavior matters.
ENCRYPTED_FIELD_KEYS = [base64.urlsafe_b64encode(os.urandom(32)).decode()]
