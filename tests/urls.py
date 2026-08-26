from django.urls import include, path

urlpatterns = [
    path("api/", include("integrations.api.urls")),
    path("integrations/", include("integrations.urls")),
]
