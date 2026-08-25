from integrations.base import Integration
from integrations.exceptions import (
    DuplicateIntegrationError,
    IntegrationNotRegisteredError,
)

_registry: dict[str, type[Integration]] = {}


def register(integration_cls: type[Integration]) -> type[Integration]:
    """
    Register an Integration subclass. Usable as a bare decorator:

        @register
        class ZoomIntegration(Integration):
            slug = "zoom"
            ...

    Re-registering the exact same class is a no-op. A different class
    claiming an already-used slug raises DuplicateIntegrationError.
    """
    slug = integration_cls.slug
    existing = _registry.get(slug)
    if existing is not None and existing is not integration_cls:
        raise DuplicateIntegrationError(slug)
    _registry[slug] = integration_cls
    return integration_cls


def unregister(slug: str) -> None:
    try:
        del _registry[slug]
    except KeyError:
        raise IntegrationNotRegisteredError(slug) from None


def get(slug: str) -> type[Integration]:
    try:
        return _registry[slug]
    except KeyError:
        raise IntegrationNotRegisteredError(slug) from None


def all() -> list[type[Integration]]:
    return [integration_cls for _, integration_cls in sorted(_registry.items())]
