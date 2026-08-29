import pytest
from django.contrib.sites.models import Site

from integrations import Integration, registry
from integrations.api.serializers import (
    serialize_configuration,
    serialize_integration_summary,
)
from integrations.fields import SecretField, TextField
from integrations.scopes import IntegrationScope
from integrations.services import credentials as services


class ExampleApiIntegration(Integration):
    slug = "example-api"
    name = "Example API"
    description = "An example."
    fields = [
        TextField("account_id", required=True),
        SecretField("api_key", required=True),
    ]


@pytest.fixture
def registered(clean_registry):
    registry.register(ExampleApiIntegration)


@pytest.fixture
def site(db):
    return Site.objects.get_or_create(
        domain="example.com", defaults={"name": "Example"}
    )[0]


@pytest.fixture
def scope(site):
    return IntegrationScope(site=site)


class TestSerializeIntegrationSummary:
    def test_shape(self, registered, scope):
        result = serialize_integration_summary(ExampleApiIntegration, scope)
        assert result["slug"] == "example-api"
        assert result["name"] == "Example API"
        assert result["description"] == "An example."
        assert result["configured"] is False
        field_names = {f["name"] for f in result["fields"]}
        assert field_names == {"account_id", "api_key"}

    def test_never_includes_a_value_or_per_field_configured(self, registered, scope):
        result = serialize_integration_summary(ExampleApiIntegration, scope)
        for field in result["fields"]:
            assert "value" not in field
            assert "configured" not in field

    def test_configured_reflects_stored_state(self, registered, scope):
        services.save_config(
            scope, "example-api", {"account_id": "acct-1", "api_key": "sekrit"}
        )
        result = serialize_integration_summary(ExampleApiIntegration, scope)
        assert result["configured"] is True


class TestSerializeConfiguration:
    def test_config_field_includes_value(self, registered, scope):
        services.save_config(
            scope, "example-api", {"account_id": "acct-1", "api_key": "sekrit"}
        )
        config = services.get_config(scope, "example-api")
        result = serialize_configuration(config, is_configured=True)

        account_id_entry = next(
            f for f in result["fields"] if f["name"] == "account_id"
        )
        assert account_id_entry["value"] == "acct-1"

    def test_secret_field_never_includes_value(self, registered, scope):
        services.save_config(
            scope, "example-api", {"account_id": "acct-1", "api_key": "sekrit"}
        )
        config = services.get_config(scope, "example-api")
        result = serialize_configuration(config, is_configured=True)

        api_key_entry = next(f for f in result["fields"] if f["name"] == "api_key")
        assert "value" not in api_key_entry
        assert api_key_entry["configured"] is True
        assert "sekrit" not in str(result)

    def test_unconfigured_state(self, registered, scope):
        config = services.get_config(scope, "example-api")
        result = serialize_configuration(config, is_configured=False)
        assert result["configured"] is False
        api_key_entry = next(f for f in result["fields"] if f["name"] == "api_key")
        assert api_key_entry["configured"] is False
