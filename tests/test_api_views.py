import json

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.sites.models import Site
from django.test import Client

from integrations import Integration, registry
from integrations.capabilities import TEST_CONNECTION, ConnectionTestResult
from integrations.fields import SecretField, TextField


class WidgetIntegration(Integration):
    slug = "widget"
    name = "Widget"
    description = "A widget integration."
    fields = [
        TextField("account_id", required=True),
        SecretField("api_key", required=True),
        SecretField("webhook_secret", required=False),
    ]


class TestableWidgetIntegration(Integration):
    # Not a pytest test class - see the note in test_credential_service.py.
    __test__ = False

    slug = "testable-widget"
    name = "Testable Widget"
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
    registry.register(WidgetIntegration)


@pytest.fixture
def registered_testable(clean_registry):
    registry.register(TestableWidgetIntegration)


@pytest.fixture
def site(db):
    return Site.objects.get_or_create(
        domain="example.com", defaults={"name": "Example"}
    )[0]


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


LIST_URL = "/api/v1/integrations/"
DETAIL_URL = "/api/v1/integrations/widget/"
CONFIG_URL = "/api/v1/integrations/widget/configuration/"
TEST_URL = "/api/v1/integrations/widget/test/"
TESTABLE_DETAIL_URL = "/api/v1/integrations/testable-widget/"
TESTABLE_CONFIG_URL = "/api/v1/integrations/testable-widget/configuration/"
TESTABLE_TEST_URL = "/api/v1/integrations/testable-widget/test/"
MISSING_DETAIL_URL = "/api/v1/integrations/does-not-exist/"
MISSING_CONFIG_URL = "/api/v1/integrations/does-not-exist/configuration/"


class TestAuthenticationRequired:
    def test_list_requires_authentication(self, registered, client):
        response = client.get(LIST_URL)
        assert response.status_code == 401
        assert response["Content-Type"] == "application/problem+json"

    def test_detail_requires_authentication(self, registered, client):
        assert client.get(DETAIL_URL).status_code == 401

    def test_configuration_requires_authentication(self, registered, client):
        assert client.get(CONFIG_URL).status_code == 401


class TestIntegrationListView:
    def test_lists_registered_integrations(self, registered, client, full_access_user):
        client.force_login(full_access_user)
        response = client.get(LIST_URL)
        assert response.status_code == 200
        body = json.loads(response.content)
        slugs = {item["slug"] for item in body["results"]}
        assert "widget" in slugs

    def test_omits_integrations_the_caller_cannot_view(
        self, registered, client, plain_user
    ):
        client.force_login(plain_user)
        response = client.get(LIST_URL)
        assert response.status_code == 200
        body = json.loads(response.content)
        assert body["results"] == []


class TestIntegrationDetailView:
    def test_returns_definition(self, registered, client, full_access_user):
        client.force_login(full_access_user)
        response = client.get(DETAIL_URL)
        assert response.status_code == 200
        body = json.loads(response.content)
        assert body["slug"] == "widget"
        assert body["capabilities"] == []

    def test_capabilities_reflect_what_the_integration_declares(
        self, registered_testable, client, full_access_user
    ):
        client.force_login(full_access_user)
        response = client.get(TESTABLE_DETAIL_URL)
        body = json.loads(response.content)
        assert body["capabilities"] == ["test_connection"]

    def test_unregistered_slug_is_404(self, registered, client, full_access_user):
        client.force_login(full_access_user)
        response = client.get(MISSING_DETAIL_URL)
        assert response.status_code == 404
        assert response["Content-Type"] == "application/problem+json"

    def test_forbidden_without_view_permission(self, registered, client, plain_user):
        client.force_login(plain_user)
        response = client.get(DETAIL_URL)
        assert response.status_code == 403


class TestConfigurationGet:
    def test_unconfigured_returns_200_with_configured_false(
        self, registered, client, full_access_user
    ):
        client.force_login(full_access_user)
        response = client.get(CONFIG_URL)
        assert response.status_code == 200
        body = json.loads(response.content)
        assert body["configured"] is False

    def test_unregistered_slug_is_404(self, registered, client, full_access_user):
        client.force_login(full_access_user)
        assert client.get(MISSING_CONFIG_URL).status_code == 404

    def test_forbidden_without_view_permission(self, registered, client, plain_user):
        client.force_login(plain_user)
        assert client.get(CONFIG_URL).status_code == 403


class TestConfigurationWrite:
    def _put(self, client, payload):
        return client.put(
            CONFIG_URL, data=json.dumps(payload), content_type="application/json"
        )

    def _patch(self, client, payload):
        return client.patch(
            CONFIG_URL, data=json.dumps(payload), content_type="application/json"
        )

    def test_put_creates_configuration(self, registered, client, full_access_user):
        client.force_login(full_access_user)
        response = self._put(client, {"account_id": "acct-1", "api_key": "sekrit"})
        assert response.status_code == 200
        body = json.loads(response.content)
        assert body["configured"] is True
        account_id_entry = next(f for f in body["fields"] if f["name"] == "account_id")
        assert account_id_entry["value"] == "acct-1"
        assert "sekrit" not in response.content.decode()

    def test_patch_updates_one_field_preserving_others(
        self, registered, client, full_access_user
    ):
        client.force_login(full_access_user)
        self._put(client, {"account_id": "acct-1", "api_key": "sekrit"})
        response = self._patch(client, {"account_id": "acct-2"})
        assert response.status_code == 200
        body = json.loads(response.content)
        account_id_entry = next(f for f in body["fields"] if f["name"] == "account_id")
        api_key_entry = next(f for f in body["fields"] if f["name"] == "api_key")
        assert account_id_entry["value"] == "acct-2"
        assert api_key_entry["configured"] is True

    def test_missing_required_field_is_422_with_errors(
        self, registered, client, full_access_user
    ):
        client.force_login(full_access_user)
        response = self._put(client, {"account_id": "acct-1"})
        assert response.status_code == 422
        body = json.loads(response.content)
        assert "api_key" in body["errors"]

    def test_null_clears_an_optional_secret(self, registered, client, full_access_user):
        client.force_login(full_access_user)
        self._put(
            client,
            {
                "account_id": "acct-1",
                "api_key": "sekrit",
                "webhook_secret": "hook",
            },
        )
        response = self._patch(client, {"webhook_secret": None})
        assert response.status_code == 200
        body = json.loads(response.content)
        webhook_entry = next(f for f in body["fields"] if f["name"] == "webhook_secret")
        assert webhook_entry["configured"] is False

    def test_null_on_non_secret_field_is_422(
        self, registered, client, full_access_user
    ):
        client.force_login(full_access_user)
        self._put(client, {"account_id": "acct-1", "api_key": "sekrit"})
        response = self._patch(client, {"account_id": None})
        assert response.status_code == 422

    def test_malformed_json_is_400(self, registered, client, full_access_user):
        client.force_login(full_access_user)
        response = client.put(
            CONFIG_URL, data="not json", content_type="application/json"
        )
        assert response.status_code == 400

    def test_unregistered_slug_is_404(self, registered, client, full_access_user):
        client.force_login(full_access_user)
        response = client.put(
            MISSING_CONFIG_URL,
            data=json.dumps({}),
            content_type="application/json",
        )
        assert response.status_code == 404

    def test_forbidden_without_configure_permission(
        self, registered, client, plain_user
    ):
        client.force_login(plain_user)
        response = self._put(client, {"account_id": "acct-1", "api_key": "sekrit"})
        assert response.status_code == 403


class TestConfigurationDelete:
    def test_delete_is_idempotent(self, registered, client, full_access_user):
        client.force_login(full_access_user)
        client.put(
            CONFIG_URL,
            data=json.dumps({"account_id": "acct-1", "api_key": "sekrit"}),
            content_type="application/json",
        )
        first = client.delete(CONFIG_URL)
        second = client.delete(CONFIG_URL)
        assert first.status_code == 204
        assert second.status_code == 204

    def test_forbidden_without_delete_permission(self, registered, client, plain_user):
        client.force_login(plain_user)
        response = client.delete(CONFIG_URL)
        assert response.status_code == 403


class TestTestConnectionView:
    def test_unsupported_capability_is_404(self, registered, client, full_access_user):
        client.force_login(full_access_user)
        response = client.post(TEST_URL)
        assert response.status_code == 404
        assert response["Content-Type"] == "application/problem+json"

    def test_success_result(self, registered_testable, client, full_access_user):
        client.force_login(full_access_user)
        client.put(
            TESTABLE_CONFIG_URL,
            data=json.dumps({"account_id": "acct-1", "api_key": "good-key"}),
            content_type="application/json",
        )
        response = client.post(TESTABLE_TEST_URL)
        assert response.status_code == 200
        body = json.loads(response.content)
        assert body == {"success": True, "message": "Connected!"}

    def test_failure_result_is_still_200(
        self, registered_testable, client, full_access_user
    ):
        client.force_login(full_access_user)
        client.put(
            TESTABLE_CONFIG_URL,
            data=json.dumps({"account_id": "acct-1", "api_key": "bad-key"}),
            content_type="application/json",
        )
        response = client.post(TESTABLE_TEST_URL)
        assert response.status_code == 200
        body = json.loads(response.content)
        assert body == {"success": False, "message": "Invalid API key."}

    def test_forbidden_without_test_connection_permission(
        self, registered_testable, client, plain_user
    ):
        client.force_login(plain_user)
        response = client.post(TESTABLE_TEST_URL)
        assert response.status_code == 403

    def test_requires_authentication(self, registered_testable, client):
        assert client.post(TESTABLE_TEST_URL).status_code == 401

    def test_get_not_allowed(self, registered_testable, client, full_access_user):
        client.force_login(full_access_user)
        response = client.get(TESTABLE_TEST_URL)
        assert response.status_code == 405


class TestMethodNotAllowed:
    def test_unsupported_method_returns_problem_details(
        self, registered, client, full_access_user
    ):
        client.force_login(full_access_user)
        response = client.post(DETAIL_URL)
        assert response.status_code == 405
        assert response["Content-Type"] == "application/problem+json"


@pytest.mark.django_db
class TestCsrfProtection:
    def test_put_without_csrf_token_is_rejected(self, registered, full_access_user):
        strict_client = Client(enforce_csrf_checks=True)
        strict_client.force_login(full_access_user)
        response = strict_client.put(
            CONFIG_URL,
            data=json.dumps({"account_id": "acct-1", "api_key": "sekrit"}),
            content_type="application/json",
        )
        assert response.status_code == 403
