from django.urls import path

from integrations.api import views

# Names are prefixed "api-" so they never collide with integrations.urls'
# (the HTML views) - both modules are meant to be included simultaneously
# by a host app, and Django's reverse() resolves a same-named pattern from
# whichever urlconf happened to be registered last, which is exactly the
# kind of mount-order-dependent bug this avoids rather than risks.
urlpatterns = [
    path(
        "v1/integrations/",
        views.IntegrationListView.as_view(),
        name="api-integration-list",
    ),
    path(
        "v1/integrations/<slug:slug>/",
        views.IntegrationDetailView.as_view(),
        name="api-integration-detail",
    ),
    path(
        "v1/integrations/<slug:slug>/configuration/",
        views.ConfigurationView.as_view(),
        name="api-integration-configuration",
    ),
    path(
        "v1/integrations/<slug:slug>/test/",
        views.TestConnectionView.as_view(),
        name="api-integration-test",
    ),
    path(
        "v1/openapi.json",
        views.OpenAPISchemaView.as_view(),
        name="api-openapi-schema",
    ),
]
