import logging
from typing import Any, cast

from django.db import transaction

from integrations.base import Integration, IntegrationConfig
from integrations.capabilities import TEST_CONNECTION, ConnectionTestResult
from integrations.exceptions import (
    CapabilityNotSupportedError,
    IntegrationValidationError,
)
from integrations.models import Credential
from integrations.registry import get as get_integration
from integrations.scopes import IntegrationScope

logger = logging.getLogger(__name__)


def get_credential(scope: IntegrationScope, slug: str) -> Credential | None:
    """Raw lookup, no validation. None if nothing is stored yet."""
    get_integration(slug)  # raises IntegrationNotRegisteredError if unknown
    return Credential.objects.filter(site=scope.site, integration=slug).first()


def get_config(scope: IntegrationScope, slug: str) -> IntegrationConfig:
    """
    Always returns an IntegrationConfig, even when nothing is stored yet
    (empty config/secrets) - callers don't need a None-check just to ask
    "what's configured". `.to_api_metadata()` is the safe, values-stripped
    view for anything reaching an HTTP response or template.
    """
    integration_cls = get_integration(slug)
    credential = Credential.objects.filter(site=scope.site, integration=slug).first()
    if credential is None:
        return IntegrationConfig(integration=integration_cls, config={}, secrets={})
    return IntegrationConfig(
        integration=integration_cls,
        config=dict(credential.config),
        # django-stubs types EncryptedJSONField's Python value as str,
        # inherited from its TextField base (chosen for its DB column type,
        # not its stubbed value type) - the runtime value is always a dict.
        secrets=dict(cast(dict, credential.secrets)),
    )


def is_configured(scope: IntegrationScope, slug: str) -> bool:
    get_integration(slug)
    return Credential.objects.filter(site=scope.site, integration=slug).exists()


def _merge_with_stored(
    integration_cls: type[Integration],
    data: dict[str, Any],
    credential: Credential | None,
) -> dict[str, Any]:
    """
    Build the full payload to validate: caller-supplied values take
    precedence; a key the caller omitted falls back to whatever's
    currently stored (secrets and config alike), so a partial update only
    changes what was actually sent. CLEAR always passes through
    untouched - Integration.clean() already understands it.
    """
    merged: dict[str, Any] = {}
    for field in integration_cls.get_fields():
        if field.name in data:
            merged[field.name] = data[field.name]
        elif credential is not None:
            # See the type: cast note in get_config() above re: EncryptedJSONField.
            stored: dict[str, Any] = (
                cast(dict, credential.secrets) if field.is_secret else credential.config
            )
            if field.name in stored:
                merged[field.name] = stored[field.name]
    return merged


def save_config(scope: IntegrationScope, slug: str, data: dict[str, Any]) -> Credential:
    """
    Validates `data` (raising IntegrationValidationError on failure) and
    persists it:
      - a field present in `data` replaces the stored value
      - a field omitted from `data` preserves whatever's currently stored
      - CLEAR (secrets only) removes the stored value; clearing a
        *required* secret with no replacement value is rejected

    Works for both first-time create and update - if nothing is stored
    yet, "preserve" has nothing to fall back on, so an omitted required
    field raises exactly like a fresh Integration.clean() call would.
    """
    integration_cls = get_integration(slug)

    with transaction.atomic():
        credential = (
            Credential.objects.select_for_update()
            .filter(site=scope.site, integration=slug)
            .first()
        )

        merged = _merge_with_stored(integration_cls, data, credential)
        result = integration_cls.clean(merged)

        required_cleared = [
            name
            for name in result.cleared_secrets
            if integration_cls.get_field(name).required
        ]
        if required_cleared:
            raise IntegrationValidationError(
                {
                    name: [
                        "This secret is required and cannot be cleared "
                        "without providing a replacement value."
                    ]
                    for name in required_cleared
                }
            )

        if credential is None:
            credential = Credential(site=scope.site, integration=slug)

        credential.config = result.config
        credential.secrets = result.secrets
        credential.save()

    return credential


def delete_config(scope: IntegrationScope, slug: str) -> bool:
    """Deletes the Credential row if present. Idempotent: returns whether
    anything was actually deleted."""
    get_integration(slug)
    deleted_count, _ = Credential.objects.filter(
        site=scope.site, integration=slug
    ).delete()
    return deleted_count > 0


def test_connection(scope: IntegrationScope, slug: str) -> ConnectionTestResult:
    """
    Runs the integration's test_connection() against the currently stored
    configuration. Never raises for provider/network failures - those
    come back as a failed ConnectionTestResult; the exception itself is
    logged in full server-side (for operator debugging) but never
    forwarded to the caller, since it may originate from arbitrary
    third-party provider code and could embed a credential.
    """
    integration_cls = get_integration(slug)
    if TEST_CONNECTION not in integration_cls.capabilities:
        raise CapabilityNotSupportedError(slug)

    if not is_configured(scope, slug):
        return ConnectionTestResult(success=False, message="Not configured yet.")

    config = get_config(scope, slug)
    try:
        return integration_cls.test_connection(config)
    except Exception:
        logger.exception("test_connection failed unexpectedly for %r", slug)
        return ConnectionTestResult(
            success=False, message="Connection test failed unexpectedly."
        )


__all__ = [
    "get_credential",
    "get_config",
    "is_configured",
    "save_config",
    "delete_config",
    "test_connection",
]
