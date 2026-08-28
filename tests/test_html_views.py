import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.sites.models import Site

from integrations import Integration, registry
from integrations.capabilities import TEST_CONNECTION, ConnectionTestResult
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


class TestableWidgetHtmlIntegration(Integration):
    # Not a pytest test class - see the note in test_credential_service.py.
    __test__ = False

    slug = "testable-widget-html"
    name = "Testable Widget HTML"
    capabilities = (TEST_CONNECTION,)
    fields = [
        TextField("account_id", required=True),
        SecretField("api_key", required=True),
    ]

    @classmethod
    def test_connection(cls, config):
        if config.secrets.get("api_key") == "bad-key":
            return ConnectionTestResult(success=False, message="Invalid API key.")
        return ConnectionTestResult(success=True, message="Connected!")


@pytest.fixture
def registered(clean_registry):
    registry.register(WidgetHtmlIntegration)


@pytest.fixture
def registered_testable(clean_registry):
    registry.register(TestableWidgetHtmlIntegration)


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


@pytest.fixture
def view_only_user(db):
    user = get_user_model().objects.create_user(username="carol", password="x")
    permission = Permission.objects.get(
        content_type__app_label="integrations", codename="view_credential"
    )
    user.user_permissions.add(permission)
    return get_user_model().objects.get(pk=user.pk)


LIST_URL = "/integrations/"
DETAIL_URL = "/integrations/widget-html/"
CONFIGURE_URL = "/integrations/widget-html/configure/"
DELETE_URL = "/integrations/widget-html/delete/"
MISSING_DETAIL_URL = "/integrations/does-not-exist/"

TESTABLE_DETAIL_URL = "/integrations/testable-widget-html/"
TESTABLE_CONFIGURE_URL = "/integrations/testable-widget-html/configure/"
TESTABLE_TEST_URL = "/integrations/testable-widget-html/test/"


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


class TestTestConnectionButtonVisibility:
    def test_hidden_when_capability_not_declared(
        self, registered, client, full_access_user, scope
    ):
        services.save_config(
            scope, "widget-html", {"account_id": "acct-1", "api_key": "sekrit"}
        )
        client.force_login(full_access_user)
        response = client.get(DETAIL_URL)
        assert "Test Connection" not in response.content.decode()

    def test_hidden_when_not_configured(
        self, registered_testable, client, full_access_user
    ):
        client.force_login(full_access_user)
        response = client.get(TESTABLE_DETAIL_URL)
        assert "Test Connection" not in response.content.decode()

    def test_hidden_when_lacking_test_connection_permission_specifically(
        self, registered_testable, client, view_only_user, scope
    ):
        # view_only_user can see the page (view_credential) but doesn't
        # have change_credential, which can_test_connection maps to by
        # default (Phase 7) - isolates the button's own gating from the
        # page's own view-permission gating.
        services.save_config(
            scope,
            "testable-widget-html",
            {"account_id": "acct-1", "api_key": "sekrit"},
        )
        client.force_login(view_only_user)
        response = client.get(TESTABLE_DETAIL_URL)
        assert response.status_code == 200
        assert "Test Connection" not in response.content.decode()

    def test_shown_when_capability_configured_and_permitted(
        self, registered_testable, client, full_access_user, scope
    ):
        services.save_config(
            scope,
            "testable-widget-html",
            {"account_id": "acct-1", "api_key": "sekrit"},
        )
        client.force_login(full_access_user)
        response = client.get(TESTABLE_DETAIL_URL)
        assert "Test Connection" in response.content.decode()


class TestTestConnectionViewPost:
    def test_unsupported_capability_is_404(self, registered, client, full_access_user):
        client.force_login(full_access_user)
        response = client.post("/integrations/widget-html/test/")
        assert response.status_code == 404

    def test_success_flashes_message_and_redirects(
        self, registered_testable, client, full_access_user, scope
    ):
        services.save_config(
            scope,
            "testable-widget-html",
            {"account_id": "acct-1", "api_key": "good-key"},
        )
        client.force_login(full_access_user)
        response = client.post(TESTABLE_TEST_URL, follow=True)
        assert response.status_code == 200
        assert "Connected!" in response.content.decode()

    def test_failure_flashes_message_and_redirects(
        self, registered_testable, client, full_access_user, scope
    ):
        services.save_config(
            scope,
            "testable-widget-html",
            {"account_id": "acct-1", "api_key": "bad-key"},
        )
        client.force_login(full_access_user)
        response = client.post(TESTABLE_TEST_URL, follow=True)
        assert response.status_code == 200
        assert "Invalid API key." in response.content.decode()

    def test_forbidden_without_permission(
        self, registered_testable, client, plain_user, scope
    ):
        services.save_config(
            scope,
            "testable-widget-html",
            {"account_id": "acct-1", "api_key": "sekrit"},
        )
        client.force_login(plain_user)
        assert client.post(TESTABLE_TEST_URL).status_code == 403
