from typing import TYPE_CHECKING, Callable

from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

if TYPE_CHECKING:
    from django.http import HttpRequest

    from integrations.permissions import IntegrationPermissionPolicy
    from integrations.scopes import IntegrationScope

DEFAULT_SCOPE_RESOLVER = "integrations.scopes.default_scope_resolver"
DEFAULT_PERMISSION_POLICY = "integrations.permissions.IntegrationPermissionPolicy"


def get_encrypted_field_keys() -> list:
    return getattr(settings, "ENCRYPTED_FIELD_KEYS", None) or []


def get_multi_fernet() -> MultiFernet:
    """
    Build a MultiFernet from settings.ENCRYPTED_FIELD_KEYS, resolved fresh
    on every call (never cached) so key rotation and @override_settings
    both take effect immediately rather than only at field-definition time.

    The first key is the primary key: MultiFernet.encrypt() always uses it,
    while MultiFernet.decrypt() tries every key in order. To rotate keys:
    prepend the new key, keep the old one(s), run the rotate_encryption_keys
    management command, then remove the retired key once satisfied.
    """
    keys = get_encrypted_field_keys()
    if not keys:
        raise ImproperlyConfigured(
            "ENCRYPTED_FIELD_KEYS must be set in Django settings as a "
            "non-empty list of base64-encoded Fernet keys."
        )
    try:
        fernets = [
            Fernet(key.encode() if isinstance(key, str) else key) for key in keys
        ]
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured(
            f"ENCRYPTED_FIELD_KEYS contains an invalid Fernet key: {exc}"
        ) from exc
    return MultiFernet(fernets)


def get_scope_resolver() -> "Callable[[HttpRequest], IntegrationScope]":
    """
    Resolve INTEGRATIONS_SCOPE_RESOLVER (a dotted path to a callable taking
    an HttpRequest and returning an IntegrationScope), resolved fresh on
    every call - not cached, same reasoning as get_multi_fernet(). Defaults
    to the built-in Django-Sites-based resolver.
    """
    path = getattr(settings, "INTEGRATIONS_SCOPE_RESOLVER", DEFAULT_SCOPE_RESOLVER)
    try:
        return import_string(path)
    except ImportError as exc:
        raise ImproperlyConfigured(
            f"INTEGRATIONS_SCOPE_RESOLVER={path!r} could not be imported: {exc}"
        ) from exc


def resolve_scope(request: "HttpRequest") -> "IntegrationScope":
    return get_scope_resolver()(request)


def get_permission_policy() -> "IntegrationPermissionPolicy":
    """
    Resolve INTEGRATIONS_PERMISSION_POLICY (a dotted path to an
    IntegrationPermissionPolicy subclass), resolved fresh on every call.
    Defaults to the built-in Django-permissions-based policy.
    """
    path = getattr(
        settings, "INTEGRATIONS_PERMISSION_POLICY", DEFAULT_PERMISSION_POLICY
    )
    try:
        policy_cls = import_string(path)
    except ImportError as exc:
        raise ImproperlyConfigured(
            f"INTEGRATIONS_PERMISSION_POLICY={path!r} could not be imported: {exc}"
        ) from exc
    return policy_cls()
