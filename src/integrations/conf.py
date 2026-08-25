from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


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
