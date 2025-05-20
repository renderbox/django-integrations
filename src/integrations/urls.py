from django.urls import path

from integrations import views

urlpatterns = [
    path("", views.DjangoIntegrationsIndexView.as_view(), name="integrations-index"),
]
