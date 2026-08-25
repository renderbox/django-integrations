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
from integrations.scopes import IntegrationScope
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


@pytest.fixture
def scope(site):
    return IntegrationScope(site=site)


def _raw_secrets(pk):
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT secrets FROM {Credential._meta.db_table} WHERE id=%s", [pk]
        )
        return cursor.fetchone()[0]


class TestSaveConfigCreate:
    def test_creates_credential_with_split_config_and_secrets(
        self, registered, scope, site
    ):
        cred = services.save_config(
            scope,
            "example-service",
            {"account_id": "acct-1", "api_key": "sekrit"},
        )
        assert cred.pk is not None
        assert cred.site == site
        assert cred.integration == "example-service"
        assert cred.config == {"account_id": "acct-1"}
        assert cred.secrets == {"api_key": "sekrit"}

    def test_missing_required_field_raises_and_creates_no_row(self, registered, scope):
        with pytest.raises(IntegrationValidationError):
            services.save_config(scope, "example-service", {"account_id": "acct-1"})
        assert services.is_configured(scope, "example-service") is False
        assert services.get_credential(scope, "example-service") is None


class TestSaveConfigUpdate:
    def _create(self, scope):
        return services.save_config(
            scope,
            "example-service",
            {"account_id": "acct-1", "api_key": "sekrit"},
        )

    def test_omitting_secret_preserves_it_but_reencrypts(self, registered, scope):
        cred = self._create(scope)
        raw_before = _raw_secrets(cred.pk)

        updated = services.save_config(
            scope, "example-service", {"account_id": "acct-2"}
        )

        assert updated.pk == cred.pk
        assert updated.config == {"account_id": "acct-2"}
        assert updated.secrets == {"api_key": "sekrit"}
        raw_after = _raw_secrets(updated.pk)
        assert (
            raw_before != raw_after
        ), "secret should be re-encrypted even though the plaintext is unchanged"

    def test_omitting_config_field_preserves_it(self, registered, scope):
        cred = self._create(scope)
        updated = services.save_config(
            scope, "example-service", {"api_key": "new-secret"}
        )
        assert updated.pk == cred.pk
        assert updated.config == {"account_id": "acct-1"}
        assert updated.secrets == {"api_key": "new-secret"}

    def test_supplying_one_field_only_changes_that_field(self, registered, scope):
        self._create(scope)
        updated = services.save_config(
            scope,
            "example-service",
            {"webhook_secret": "hook-secret"},
        )
        assert updated.config == {"account_id": "acct-1"}
        assert updated.secrets == {"api_key": "sekrit", "webhook_secret": "hook-secret"}


class TestClearSemantics:
    def _create(self, scope):
        return services.save_config(
            scope,
            "example-service",
            {
                "account_id": "acct-1",
                "api_key": "sekrit",
                "webhook_secret": "hook-secret",
            },
        )

    def test_clear_optional_secret_removes_it(self, registered, scope):
        self._create(scope)
        updated = services.save_config(
            scope, "example-service", {"webhook_secret": CLEAR}
        )
        assert "webhook_secret" not in updated.secrets
        config = services.get_config(scope, "example-service")
        assert config.is_secret_configured("webhook_secret") is False
        assert config.is_secret_configured("api_key") is True

    def test_clear_required_secret_without_replacement_raises(self, registered, scope):
        self._create(scope)
        with pytest.raises(IntegrationValidationError):
            services.save_config(scope, "example-service", {"api_key": CLEAR})

    def test_clear_on_non_secret_field_raises(self, registered, scope):
        self._create(scope)
        with pytest.raises(IntegrationValidationError):
            services.save_config(scope, "example-service", {"account_id": CLEAR})


class TestGetConfig:
    def test_unconfigured_returns_empty_integration_config(self, registered, scope):
        config = services.get_config(scope, "example-service")
        assert config.config == {}
        assert config.secrets == {}


class TestDeleteConfig:
    def test_removes_row_and_is_idempotent(self, registered, scope):
        services.save_config(
            scope, "example-service", {"account_id": "acct-1", "api_key": "sekrit"}
        )
        assert services.delete_config(scope, "example-service") is True
        assert services.is_configured(scope, "example-service") is False
        assert services.delete_config(scope, "example-service") is False


class TestUnknownSlug:
    def test_every_function_raises(self, clean_registry, scope):
        with pytest.raises(IntegrationNotRegisteredError):
            services.get_credential(scope, "does-not-exist")
        with pytest.raises(IntegrationNotRegisteredError):
            services.get_config(scope, "does-not-exist")
        with pytest.raises(IntegrationNotRegisteredError):
            services.is_configured(scope, "does-not-exist")
        with pytest.raises(IntegrationNotRegisteredError):
            services.save_config(scope, "does-not-exist", {})
        with pytest.raises(IntegrationNotRegisteredError):
            services.delete_config(scope, "does-not-exist")


class TestCrossTenantIsolation:
    @pytest.fixture
    def other_site(self, db):
        return Site.objects.get_or_create(
            domain="other.example.com", defaults={"name": "Other"}
        )[0]

    @pytest.fixture
    def other_scope(self, other_site):
        return IntegrationScope(site=other_site)

    def test_save_config_does_not_touch_other_scopes_row(
        self, registered, scope, other_scope
    ):
        services.save_config(
            scope, "example-service", {"account_id": "scope-a", "api_key": "key-a"}
        )
        services.save_config(
            other_scope,
            "example-service",
            {"account_id": "scope-b", "api_key": "key-b"},
        )

        assert services.get_config(scope, "example-service").config == {
            "account_id": "scope-a"
        }
        assert services.get_config(other_scope, "example-service").config == {
            "account_id": "scope-b"
        }

    def test_updating_one_scope_never_changes_the_other(
        self, registered, scope, other_scope
    ):
        services.save_config(
            scope, "example-service", {"account_id": "scope-a", "api_key": "key-a"}
        )
        services.save_config(
            other_scope,
            "example-service",
            {"account_id": "scope-b", "api_key": "key-b"},
        )

        services.save_config(scope, "example-service", {"account_id": "scope-a-v2"})

        assert services.get_config(scope, "example-service").config == {
            "account_id": "scope-a-v2"
        }
        assert services.get_config(other_scope, "example-service").config == {
            "account_id": "scope-b"
        }

    def test_deleting_one_scope_never_deletes_the_other(
        self, registered, scope, other_scope
    ):
        services.save_config(
            scope, "example-service", {"account_id": "scope-a", "api_key": "key-a"}
        )
        services.save_config(
            other_scope,
            "example-service",
            {"account_id": "scope-b", "api_key": "key-b"},
        )

        services.delete_config(scope, "example-service")

        assert services.is_configured(scope, "example-service") is False
        assert services.is_configured(other_scope, "example-service") is True
