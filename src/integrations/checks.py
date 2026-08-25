import re

from django.core import checks

from integrations import registry

SLUG_RE = re.compile(r"^[a-z0-9_-]+$")


@checks.register("integrations")
def check_unique_slugs(app_configs, **kwargs):
    """
    Defense in depth: register() already refuses a second class for an
    already-used slug, so this should be unreachable in normal use. Kept
    in case the registry is ever mutated outside register().
    """
    errors = []
    by_slug: dict[str, list] = {}
    for integration in registry.all():
        by_slug.setdefault(integration.slug, []).append(integration)

    for slug, integration_classes in by_slug.items():
        if len(integration_classes) > 1:
            names = ", ".join(cls.__qualname__ for cls in integration_classes)
            errors.append(
                checks.Error(
                    f"Multiple integrations are registered for slug {slug!r}: {names}.",
                    id="integrations.E001",
                )
            )
    return errors


@checks.register("integrations")
def check_slugs(app_configs, **kwargs):
    errors = []
    for integration in registry.all():
        slug = getattr(integration, "slug", None)
        if not isinstance(slug, str) or not SLUG_RE.match(slug):
            errors.append(
                checks.Error(
                    f"{integration.__qualname__}.slug must be a non-empty string of "
                    "lowercase letters, numbers, hyphens, and underscores.",
                    obj=integration,
                    id="integrations.E002",
                )
            )
    return errors


@checks.register("integrations")
def check_names(app_configs, **kwargs):
    errors = []
    for integration in registry.all():
        name = getattr(integration, "name", None)
        if not isinstance(name, str) or not name.strip():
            errors.append(
                checks.Error(
                    f"{integration.__qualname__}.name must be a non-empty string.",
                    obj=integration,
                    id="integrations.E003",
                )
            )
    return errors


@checks.register("integrations")
def check_field_definitions(app_configs, **kwargs):
    errors = []
    for integration in registry.all():
        seen_names: set[str] = set()
        for field in integration.get_fields():
            name = getattr(field, "name", None)
            if not isinstance(name, str) or not name.strip():
                errors.append(
                    checks.Error(
                        f"{integration.__qualname__} has a field with an invalid "
                        f"name {name!r}.",
                        obj=integration,
                        id="integrations.E005",
                    )
                )
                continue
            if name in seen_names:
                # Defense in depth: Integration.__init_subclass__ already
                # refuses duplicate field names at class-definition time.
                errors.append(
                    checks.Error(
                        f"{integration.__qualname__} has duplicate field name "
                        f"{name!r}.",
                        obj=integration,
                        id="integrations.E004",
                    )
                )
            seen_names.add(name)
    return errors
