from django.urls import path

from . import views

urlpatterns = [
    path("", views.CredentialsListView.as_view(), name="integration-list"),
    path("zoom/", views.ZoomFormView.as_view(), name="integration-zoom"),
    path("vouchery/", views.VoucheryFormView.as_view(), name="integration-vouchery"),
    path("authorizenet/", views.AuthorizeNetFormView.as_view(), name="integration-authorizenet"),
]
