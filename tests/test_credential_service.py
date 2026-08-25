import pytest
from django.contrib.sites.models import Site
from django.db import connection

from integrations import Integration, registry
from integrations.base import CLEAR
from integrations.exceptions import (
    IntegrationNotRegisteredError,
    IntegrationValidationError,
)
from integrations.fields import SecretField, TextField
from integrations.models import Credential
from integrations.services import credentials as services


class ExampleServiceIntegration(Integration):
    slug = "example-service"
    name = "Example Service"
    fields = [
        TextField("account_id", required=True),
        SecretField("api_key", required=True),
        SecretField("webhook_secret", required=False),
    ]


@pytest.fixture
def registered(clean_registry):
    registry.register(ExampleServiceIntegration)


@pytest.fixture
def site(db):
    return Site.objects.get_or_create(
        domain="example.com", defaults={"name": "Example"}
    )[0]


def _raw_secrets(pk):
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT secrets FROM {Credential._meta.db_table} WHERE id=%s", [pk]
        )
        return cursor.fetchone()[0]


class TestSaveConfigCreate:
    def test_creates_credential_with_split_config_and_secrets(self, registered, site):
        cred = services.save_config(
            site,
            "example-service",
            {"account_id": "acct-1", "api_key": "sekrit"},
        )
        assert cred.pk is not None
        assert cred.site == site
        assert cred.integration == "example-service"
        assert cred.config == {"account_id": "acct-1"}
        assert cred.secrets == {"api_key": "sekrit"}

    def test_missing_required_field_raises_and_creates_no_row(self, registered, site):
        with pytest.raises(IntegrationValidationError):
            services.save_config(site, "example-service", {"account_id": "acct-1"})
        assert services.is_configured(site, "example-service") is False
        assert services.get_credential(site, "example-service") is None


class TestSaveConfigUpdate:
    def _create(self, site):
        return services.save_config(
            site,
            "example-service",
            {"account_id": "acct-1", "api_key": "sekrit"},
        )

    def test_omitting_secret_preserves_it_but_reencrypts(self, registered, site):
        cred = self._create(site)
        raw_before = _raw_secrets(cred.pk)

        updated = services.save_config(
            site, "example-service", {"account_id": "acct-2"}
        )

        assert updated.pk == cred.pk
        assert updated.config == {"account_id": "acct-2"}
        assert updated.secrets == {"api_key": "sekrit"}
        raw_after = _raw_secrets(updated.pk)
        assert (
            raw_before != raw_after
        ), "secret should be re-encrypted even though the plaintext is unchanged"

    def test_omitting_config_field_preserves_it(self, registered, site):
        cred = self._create(site)
        updated = services.save_config(
            site, "example-service", {"api_key": "new-secret"}
        )
        assert updated.pk == cred.pk
        assert updated.config == {"account_id": "acct-1"}
        assert updated.secrets == {"api_key": "new-secret"}

    def test_supplying_one_field_only_changes_that_field(self, registered, site):
        self._create(site)
        updated = services.save_config(
            site,
            "example-service",
            {"webhook_secret": "hook-secret"},
        )
        assert updated.config == {"account_id": "acct-1"}
        assert updated.secrets == {"api_key": "sekrit", "webhook_secret": "hook-secret"}


class TestClearSemantics:
    def _create(self, site):
        return services.save_config(
            site,
            "example-service",
            {
                "account_id": "acct-1",
                "api_key": "sekrit",
                "webhook_secret": "hook-secret",
            },
        )

    def test_clear_optional_secret_removes_it(self, registered, site):
        self._create(site)
        updated = services.save_config(
            site, "example-service", {"webhook_secret": CLEAR}
        )
        assert "webhook_secret" not in updated.secrets
        config = services.get_config(site, "example-service")
        assert config.is_secret_configured("webhook_secret") is False
        assert config.is_secret_configured("api_key") is True

    def test_clear_required_secret_without_replacement_raises(self, registered, site):
        self._create(site)
        with pytest.raises(IntegrationValidationError):
            services.save_config(site, "example-service", {"api_key": CLEAR})

    def test_clear_on_non_secret_field_raises(self, registered, site):
        self._create(site)
        with pytest.raises(IntegrationValidationError):
            services.save_config(site, "example-service", {"account_id": CLEAR})


class TestGetConfig:
    def test_unconfigured_returns_empty_integration_config(self, registered, site):
        config = services.get_config(site, "example-service")
        assert config.config == {}
        assert config.secrets == {}


class TestDeleteConfig:
    def test_removes_row_and_is_idempotent(self, registered, site):
        services.save_config(
            site, "example-service", {"account_id": "acct-1", "api_key": "sekrit"}
        )
        assert services.delete_config(site, "example-service") is True
        assert services.is_configured(site, "example-service") is False
        assert services.delete_config(site, "example-service") is False


class TestUnknownSlug:
    def test_every_function_raises(self, clean_registry, site):
        with pytest.raises(IntegrationNotRegisteredError):
            services.get_credential(site, "does-not-exist")
        with pytest.raises(IntegrationNotRegisteredError):
            services.get_config(site, "does-not-exist")
        with pytest.raises(IntegrationNotRegisteredError):
            services.is_configured(site, "does-not-exist")
        with pytest.raises(IntegrationNotRegisteredError):
            services.save_config(site, "does-not-exist", {})
        with pytest.raises(IntegrationNotRegisteredError):
            services.delete_config(site, "does-not-exist")
