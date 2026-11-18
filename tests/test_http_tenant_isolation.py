"""
Tenant isolation through the HTTP interfaces (JSON API and HTML views).

The service layer's own isolation is covered in test_credential_service.py;
these tests prove the views resolve the request's scope and never reach
another site's credential: a request on the current site (SITE_ID) can't
read, change or delete what another site has stored.
"""

import json

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.sites.models import Site

from integrations import Integration, registry, services
from integrations.fields import SecretField, TextField
from integrations.scopes import IntegrationScope


class IsolatedIntegration(Integration):
    slug = "isolated"
    name = "Isolated"
    fields = [
        TextField("account_id", required=True),
        SecretField("api_key", required=True),
    ]


OTHER_ACCOUNT = "other-site-account"
OTHER_SECRET = "OTHER-SITE-SECRET"

API_CONFIG_URL = "/api/v1/integrations/isolated/configuration/"
HTML_DETAIL_URL = "/integrations/isolated/"
HTML_CONFIGURE_URL = "/integrations/isolated/configure/"
HTML_DELETE_URL = "/integrations/isolated/delete/"


@pytest.fixture
def registered(clean_registry):
    registry.register(IsolatedIntegration)


@pytest.fixture
def current_scope(db):
    return IntegrationScope(site=Site.objects.get_current())


@pytest.fixture
def other_scope(registered, db):
    other_site = Site.objects.create(domain="other.example.com", name="Other")
    scope = IntegrationScope(site=other_site)
    services.save_config(
        scope, "isolated", {"account_id": OTHER_ACCOUNT, "api_key": OTHER_SECRET}
    )
    return scope


@pytest.fixture
def full_access_client(client, db):
    user = get_user_model().objects.create_user(username="alice", password="x")
    user.user_permissions.set(
        Permission.objects.filter(
            content_type__app_label="integrations",
            codename__in=["view_credential", "change_credential", "delete_credential"],
        )
    )
    client.force_login(user)
    return client


def assert_other_site_untouched(other_scope):
    stored = services.get_config(other_scope, "isolated")
    assert stored.config == {"account_id": OTHER_ACCOUNT}
    assert stored.secrets == {"api_key": OTHER_SECRET}


class TestApi:
    def test_read_does_not_see_another_sites_configuration(
        self, full_access_client, other_scope
    ):
        response = full_access_client.get(API_CONFIG_URL)
        assert response.status_code == 200
        assert json.loads(response.content)["configured"] is False
        assert OTHER_ACCOUNT not in response.content.decode()

    def test_write_creates_the_current_sites_own_configuration(
        self, full_access_client, other_scope, current_scope
    ):
        response = full_access_client.patch(
            API_CONFIG_URL,
            data=json.dumps({"account_id": "mine", "api_key": "my-key"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        assert services.get_config(current_scope, "isolated").config == {
            "account_id": "mine"
        }
        assert_other_site_untouched(other_scope)

    def test_delete_leaves_another_sites_configuration(
        self, full_access_client, other_scope
    ):
        assert full_access_client.delete(API_CONFIG_URL).status_code == 204
        assert_other_site_untouched(other_scope)


class TestHtml:
    def test_detail_does_not_show_another_sites_configuration(
        self, full_access_client, other_scope
    ):
        response = full_access_client.get(HTML_DETAIL_URL)
        assert response.status_code == 200
        assert OTHER_ACCOUNT not in response.content.decode()

    def test_configure_form_is_not_prefilled_from_another_site(
        self, full_access_client, other_scope
    ):
        response = full_access_client.get(HTML_CONFIGURE_URL)
        assert response.status_code == 200
        assert OTHER_ACCOUNT not in response.content.decode()

    def test_configure_saves_to_the_current_site_only(
        self, full_access_client, other_scope, current_scope
    ):
        response = full_access_client.post(
            HTML_CONFIGURE_URL, data={"account_id": "mine", "api_key": "my-key"}
        )
        assert response.status_code == 302
        assert services.get_config(current_scope, "isolated").config == {
            "account_id": "mine"
        }
        assert_other_site_untouched(other_scope)

    def test_delete_leaves_another_sites_configuration(
        self, full_access_client, other_scope
    ):
        assert full_access_client.post(HTML_DELETE_URL).status_code == 302
        assert_other_site_untouched(other_scope)
