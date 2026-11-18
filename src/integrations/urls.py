from django.urls import path

from integrations import views

urlpatterns = [
    path("", views.IntegrationListView.as_view(), name="integration-list"),
    path(
        "<slug:slug>/", views.IntegrationDetailView.as_view(), name="integration-detail"
    ),
    path(
        "<slug:slug>/configure/",
        views.ConfigureView.as_view(),
        name="integration-configure",
    ),
    path("<slug:slug>/delete/", views.DeleteView.as_view(), name="integration-delete"),
    path(
        "<slug:slug>/test/",
        views.TestConnectionView.as_view(),
        name="integration-test",
    ),
]
