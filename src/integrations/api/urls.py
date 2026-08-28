from django.urls import path

from integrations.api import views

urlpatterns = [
    path(
        "v1/integrations/",
        views.IntegrationListView.as_view(),
        name="integration-list",
    ),
    path(
        "v1/integrations/<slug:slug>/",
        views.IntegrationDetailView.as_view(),
        name="integration-detail",
    ),
    path(
        "v1/integrations/<slug:slug>/configuration/",
        views.ConfigurationView.as_view(),
        name="integration-configuration",
    ),
    path(
        "v1/integrations/<slug:slug>/test/",
        views.TestConnectionView.as_view(),
        name="integration-test",
    ),
    path(
        "v1/openapi.json",
        views.OpenAPISchemaView.as_view(),
        name="openapi-schema",
    ),
]
