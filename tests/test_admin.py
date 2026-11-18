import pytest
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site

from integrations import Integration, registry
from integrations.admin import CredentialAdmin
from integrations.fields import SecretField, TextField
from integrations.models import Credential


class WidgetAdminIntegration(Integration):
    slug = "widget-admin"
    name = "Widget Admin"
    fields = [
        TextField("account_id", required=True),
        SecretField("api_key", required=True),
        SecretField("webhook_secret", required=False),
    ]


@pytest.fixture
def registered(clean_registry):
    registry.register(WidgetAdminIntegration)


@pytest.fixture
def site(db):
    return Site.objects.get_or_create(
        domain="example.com", defaults={"name": "Example"}
    )[0]


@pytest.fixture
def credential_admin():
    from django.contrib import admin

    return CredentialAdmin(Credential, admin.site)


@pytest.fixture
def superuser(db):
    return get_user_model().objects.create_superuser(
        username="root", password="x", email="root@example.com"
    )


class TestSecretsSummary:
    def test_registered_integration_shows_field_labels(
        self, registered, site, credential_admin
    ):
        cred = Credential.objects.create(
            site=site,
            integration="widget-admin",
            secrets={"api_key": "SEKRIT-XYZ"},
        )
        summary = credential_admin.secrets_summary(cred)
        assert "Api Key: configured" in summary
        assert "Webhook Secret: not set" in summary
        assert "SEKRIT-XYZ" not in summary

    def test_unregistered_integration_falls_back_to_raw_keys(
        self, site, credential_admin
    ):
        cred = Credential.objects.create(
            site=site,
            integration="does-not-exist",
            secrets={"some_key": "SEKRIT-XYZ"},
        )
        summary = credential_admin.secrets_summary(cred)
        assert "some_key: configured" in summary
        assert "SEKRIT-XYZ" not in summary

    def test_legacy_fields_show_presence_only(self, site, credential_admin):
        cred = Credential.objects.create(
            site=site, private_key="PRIVATE-XYZ", public_key="PUBLIC-XYZ"
        )
        summary = credential_admin.secrets_summary(cred)
        assert "Legacy private_key: configured" in summary
        assert "Legacy public_key: configured" in summary
        assert "PRIVATE-XYZ" not in summary
        assert "PUBLIC-XYZ" not in summary

    def test_no_secrets_stored(self, site, credential_admin):
        cred = Credential.objects.create(site=site)
        assert credential_admin.secrets_summary(cred) == "No secrets stored"


class TestIntegrationStatus:
    def test_registered(self, registered, site, credential_admin):
        cred = Credential.objects.create(site=site, integration="widget-admin")
        assert credential_admin.integration_status(cred) == "Registered"

    def test_unregistered(self, site, credential_admin):
        cred = Credential.objects.create(site=site, integration="does-not-exist")
        assert credential_admin.integration_status(cred) == "Unregistered"

    def test_no_integration_set(self, site, credential_admin):
        cred = Credential.objects.create(site=site)
        assert credential_admin.integration_status(cred) == "—"


class TestGetReadonlyFields:
    def test_add_form_does_not_lock_integration_or_config(self, credential_admin):
        fields = credential_admin.get_readonly_fields(request=None, obj=None)
        assert "integration" not in fields
        assert "config" not in fields
        assert "secrets_summary" in fields

    def test_change_form_locks_integration_and_config(self, site, credential_admin):
        cred = Credential.objects.create(site=site, integration="widget-admin")
        fields = credential_admin.get_readonly_fields(request=None, obj=cred)
        assert "integration" in fields
        assert "config" in fields


@pytest.mark.django_db
class TestAdminHttp:
    def test_changelist_renders_with_new_columns(
        self, registered, site, client, superuser
    ):
        Credential.objects.create(
            site=site, integration="widget-admin", secrets={"api_key": "sekrit"}
        )
        client.force_login(superuser)
        response = client.get("/admin/integrations/credential/")
        assert response.status_code == 200
        body = response.content.decode()
        assert "Status" in body

    def test_change_form_never_leaks_secret_values(
        self, registered, site, client, superuser
    ):
        cred = Credential.objects.create(
            site=site,
            integration="widget-admin",
            secrets={"api_key": "SEKRIT-XYZ"},
            private_key="PRIVATE-XYZ",
            public_key="PUBLIC-XYZ",
        )
        client.force_login(superuser)
        response = client.get(f"/admin/integrations/credential/{cred.pk}/change/")
        body = response.content.decode()
        assert response.status_code == 200
        assert "SEKRIT-XYZ" not in body
        assert "PRIVATE-XYZ" not in body
        assert "PUBLIC-XYZ" not in body

    def test_excluded_fields_are_not_form_fields(
        self, registered, site, client, superuser
    ):
        cred = Credential.objects.create(site=site, integration="widget-admin")
        client.force_login(superuser)
        response = client.get(f"/admin/integrations/credential/{cred.pk}/change/")
        body = response.content.decode()
        assert 'name="secrets"' not in body
        assert 'name="public_key"' not in body
        assert 'name="private_key"' not in body
