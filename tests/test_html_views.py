import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.sites.models import Site

from integrations import Integration, registry
from integrations.fields import SecretField, TextField
from integrations.scopes import IntegrationScope
from integrations.services import credentials as services


class WidgetHtmlIntegration(Integration):
    slug = "widget-html"
    name = "Widget HTML"
    description = "A widget integration for HTML view tests."
    fields = [
        TextField("account_id", required=True),
        SecretField("api_key", required=True),
        SecretField("webhook_secret", required=False),
    ]


@pytest.fixture
def registered(clean_registry):
    registry.register(WidgetHtmlIntegration)


@pytest.fixture
def site(db):
    return Site.objects.get_or_create(
        domain="example.com", defaults={"name": "Example"}
    )[0]


@pytest.fixture
def scope(site):
    return IntegrationScope(site=site)


@pytest.fixture
def full_access_user(db):
    user = get_user_model().objects.create_user(username="alice", password="x")
    codenames = ["view_credential", "change_credential", "delete_credential"]
    permissions = Permission.objects.filter(
        content_type__app_label="integrations", codename__in=codenames
    )
    user.user_permissions.set(permissions)
    return get_user_model().objects.get(pk=user.pk)


@pytest.fixture
def plain_user(db):
    return get_user_model().objects.create_user(username="bob", password="x")


LIST_URL = "/integrations/"
DETAIL_URL = "/integrations/widget-html/"
CONFIGURE_URL = "/integrations/widget-html/configure/"
DELETE_URL = "/integrations/widget-html/delete/"
MISSING_DETAIL_URL = "/integrations/does-not-exist/"


class TestAuthenticationRequired:
    def test_list_redirects_to_login(self, registered, client):
        response = client.get(LIST_URL)
        assert response.status_code == 302
        assert response.url.startswith("/accounts/login/")

    def test_configure_redirects_to_login(self, registered, client):
        response = client.get(CONFIGURE_URL)
        assert response.status_code == 302


class TestIntegrationListView:
    def test_shows_configured_and_unconfigured(
        self, registered, client, full_access_user, scope
    ):
        services.save_config(
            scope, "widget-html", {"account_id": "acct-1", "api_key": "sekrit"}
        )
        client.force_login(full_access_user)
        response = client.get(LIST_URL)
        assert response.status_code == 200
        assert "Widget HTML" in response.content.decode()
        assert "Configured" in response.content.decode()

    def test_omits_integrations_without_view_permission(
        self, registered, client, plain_user
    ):
        client.force_login(plain_user)
        response = client.get(LIST_URL)
        assert response.status_code == 200
        assert "Widget HTML" not in response.content.decode()


class TestIntegrationDetailView:
    def test_unregistered_slug_is_404(self, registered, client, full_access_user):
        client.force_login(full_access_user)
        assert client.get(MISSING_DETAIL_URL).status_code == 404

    def test_forbidden_without_view_permission(self, registered, client, plain_user):
        client.force_login(plain_user)
        assert client.get(DETAIL_URL).status_code == 403

    def test_shows_fields_without_secret_values(
        self, registered, client, full_access_user, scope
    ):
        services.save_config(
            scope,
            "widget-html",
            {"account_id": "acct-1", "api_key": "SEKRIT-XYZ"},
        )
        client.force_login(full_access_user)
        response = client.get(DETAIL_URL)
        body = response.content.decode()
        assert response.status_code == 200
        assert "acct-1" in body
        assert "SEKRIT-XYZ" not in body


class TestConfigureViewGet:
    def test_forbidden_without_configure_permission(
        self, registered, client, plain_user
    ):
        client.force_login(plain_user)
        assert client.get(CONFIGURE_URL).status_code == 403

    def test_prefills_non_secret_but_never_secret_value(
        self, registered, client, full_access_user, scope
    ):
        services.save_config(
            scope,
            "widget-html",
            {"account_id": "acct-1", "api_key": "SEKRIT-XYZ"},
        )
        client.force_login(full_access_user)
        response = client.get(CONFIGURE_URL)
        body = response.content.decode()
        assert response.status_code == 200
        assert 'value="acct-1"' in body
        assert "SEKRIT-XYZ" not in body


class TestConfigureViewPost:
    def _post(self, client, payload):
        return client.post(CONFIGURE_URL, data=payload)

    def test_creates_configuration_and_redirects(
        self, registered, client, full_access_user
    ):
        client.force_login(full_access_user)
        response = self._post(client, {"account_id": "acct-1", "api_key": "sekrit"})
        assert response.status_code == 302
        assert response.url == DETAIL_URL

    def test_leaving_secret_blank_preserves_stored_value(
        self, registered, client, full_access_user, scope
    ):
        client.force_login(full_access_user)
        self._post(client, {"account_id": "acct-1", "api_key": "sekrit"})

        self._post(client, {"account_id": "acct-2", "api_key": ""})

        config = services.get_config(scope, "widget-html")
        assert config.config == {"account_id": "acct-2"}
        assert config.secrets == {"api_key": "sekrit"}

    def test_clear_checkbox_removes_optional_secret(
        self, registered, client, full_access_user, scope
    ):
        client.force_login(full_access_user)
        self._post(
            client,
            {
                "account_id": "acct-1",
                "api_key": "sekrit",
                "webhook_secret": "hook",
            },
        )

        self._post(
            client,
            {
                "account_id": "acct-1",
                "api_key": "",
                "webhook_secret__clear": "on",
            },
        )

        config = services.get_config(scope, "widget-html")
        assert "webhook_secret" not in config.secrets
        assert config.secrets == {"api_key": "sekrit"}

    def test_missing_required_field_rerenders_with_error(
        self, registered, client, full_access_user
    ):
        client.force_login(full_access_user)
        response = self._post(client, {"account_id": "acct-1", "api_key": ""})
        assert response.status_code == 200
        assert (
            "api_key" in response.content.decode()
            or "required" in response.content.decode().lower()
        )

    def test_forbidden_without_configure_permission(
        self, registered, client, plain_user
    ):
        client.force_login(plain_user)
        response = self._post(client, {"account_id": "acct-1", "api_key": "sekrit"})
        assert response.status_code == 403


class TestDeleteView:
    def test_get_shows_confirmation(self, registered, client, full_access_user, scope):
        services.save_config(
            scope, "widget-html", {"account_id": "acct-1", "api_key": "sekrit"}
        )
        client.force_login(full_access_user)
        response = client.get(DELETE_URL)
        assert response.status_code == 200
        assert "Widget HTML" in response.content.decode()

    def test_post_deletes_and_redirects(
        self, registered, client, full_access_user, scope
    ):
        services.save_config(
            scope, "widget-html", {"account_id": "acct-1", "api_key": "sekrit"}
        )
        client.force_login(full_access_user)
        response = client.post(DELETE_URL)
        assert response.status_code == 302
        assert response.url == LIST_URL
        assert services.is_configured(scope, "widget-html") is False

    def test_forbidden_without_delete_permission(self, registered, client, plain_user):
        client.force_login(plain_user)
        assert client.post(DELETE_URL).status_code == 403
