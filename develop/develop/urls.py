"""
Demo project URL configuration.

This mounts the package's own routes directly, at the host project's
choosing - the built-in HTML UI at the root, and the JSON API under
"api/". See docs/http-api.md and docs/html-ui.md.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include("integrations.urls")),
    path("api/", include("integrations.api.urls")),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
]
