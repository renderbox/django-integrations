from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("api/", include("integrations.api.urls")),
    path("integrations/", include("integrations.urls")),
    path("admin/", admin.site.urls),
]
