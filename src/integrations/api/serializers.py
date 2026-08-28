from typing import Any

from integrations.base import Integration, IntegrationConfig
from integrations.scopes import IntegrationScope
from integrations.services import credentials as services


def serialize_integration_summary(
    integration_cls: type[Integration], scope: IntegrationScope
) -> dict[str, Any]:
    """
    Describes an integration's definition (list/detail views) - field
    shapes only, no current values, no per-field `configured` (that's
    specific to the configuration endpoint, see serialize_configuration).
    """
    return {
        "slug": integration_cls.slug,
        "name": integration_cls.name,
        "description": integration_cls.description,
        "fields": [field.api_metadata() for field in integration_cls.get_fields()],
        "configured": services.is_configured(scope, integration_cls.slug),
        "capabilities": list(integration_cls.capabilities),
    }


def serialize_configuration(
    config: IntegrationConfig, *, is_configured: bool
) -> dict[str, Any]:
    """
    Describes the current stored configuration. Non-secret fields include
    their actual value; secret fields only ever show whether one is
    configured, never the value itself.
    """
    fields = []
    for field in config.integration.get_fields():
        entry = field.api_metadata(
            configured=(
                config.is_secret_configured(field.name) if field.is_secret else None
            )
        )
        if not field.is_secret:
            entry["value"] = config.config.get(field.name)
        fields.append(entry)
    return {
        "integration": config.integration.slug,
        "configured": is_configured,
        "fields": fields,
    }
