import pytest

from integrations import (
    CLEAR,
    Integration,
    IntegrationConfig,
    IntegrationValidationError,
)
from integrations.fields import SecretField, TextField


class ExampleIntegration(Integration):
    slug = "example"
    name = "Example"

    fields = [
        TextField("account_id", label="Account ID", required=True),
        SecretField("api_key", label="API Key", required=True),
    ]


class TestIntegrationClean:
    def test_valid_payload_returns_integration_config(self):
        result = ExampleIntegration.clean({"account_id": "acct-1", "api_key": "sekrit"})
        assert isinstance(result, IntegrationConfig)
        assert result.config == {"account_id": "acct-1"}
        assert result.secrets == {"api_key": "sekrit"}

    def test_missing_required_field_raises(self):
        with pytest.raises(IntegrationValidationError) as exc_info:
            ExampleIntegration.clean({"account_id": "acct-1"})
        assert "api_key" in exc_info.value.errors

    def test_multiple_missing_fields_are_aggregated(self):
        with pytest.raises(IntegrationValidationError) as exc_info:
            ExampleIntegration.clean({})
        assert set(exc_info.value.errors) == {"account_id", "api_key"}


class TestCrossFieldValidation:
    def test_validate_hook_can_reject_a_clean_payload(self):
        class StrictIntegration(Integration):
            slug = "strict"
            name = "Strict"
            fields = [TextField("mode", required=True)]

            @classmethod
            def validate(cls, config, secrets):
                if config["mode"] != "allowed":
                    raise IntegrationValidationError(
                        {"__all__": ["mode must be 'allowed'."]}
                    )

        with pytest.raises(IntegrationValidationError) as exc_info:
            StrictIntegration.clean({"mode": "denied"})
        assert "__all__" in exc_info.value.errors

        result = StrictIntegration.clean({"mode": "allowed"})
        assert result.config == {"mode": "allowed"}

    def test_validate_hook_not_called_when_field_validation_already_failed(self):
        calls = []

        class TrackingIntegration(Integration):
            slug = "tracking"
            name = "Tracking"
            fields = [TextField("required_field", required=True)]

            @classmethod
            def validate(cls, config, secrets):
                calls.append((config, secrets))

        with pytest.raises(IntegrationValidationError):
            TrackingIntegration.clean({})

        assert calls == []


class TestDuplicateFieldNames:
    def test_duplicate_field_names_raise_at_class_definition(self):
        with pytest.raises(IntegrationValidationError):

            class DuplicateIntegration(Integration):
                slug = "dup"
                name = "Dup"
                fields = [TextField("x"), TextField("x")]


class TestClearSemantics:
    def test_clear_on_secret_field_is_recorded(self):
        result = ExampleIntegration.clean({"account_id": "acct-1", "api_key": CLEAR})
        assert result.cleared_secrets == frozenset({"api_key"})
        assert "api_key" not in result.secrets

    def test_clear_on_non_secret_field_is_rejected(self):
        with pytest.raises(IntegrationValidationError) as exc_info:
            ExampleIntegration.clean({"account_id": CLEAR, "api_key": "sekrit"})
        assert "account_id" in exc_info.value.errors


class TestIntegrationConfigMetadata:
    def test_to_api_metadata_never_leaks_secret_values(self):
        result = ExampleIntegration.clean({"account_id": "acct-1", "api_key": "sekrit"})
        metadata = result.to_api_metadata()

        secret_entry = next(m for m in metadata if m["name"] == "api_key")
        assert "value" not in secret_entry
        assert "sekrit" not in str(secret_entry)
        assert secret_entry["configured"] is True

        text_entry = next(m for m in metadata if m["name"] == "account_id")
        assert "configured" not in text_entry
