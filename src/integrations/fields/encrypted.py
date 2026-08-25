import json

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models

from integrations.exceptions import DecryptionError


class EncryptedJSONField(models.TextField):
    """
    Stores arbitrary JSON-serializable data, encrypted at rest with Fernet
    symmetric encryption (with key rotation support via multiple
    ENCRYPTED_FIELD_KEYS).

    Deliberately a TextField, not a JSONField: on Postgres, JSONField maps
    to a native jsonb column that validates its contents are JSON at the DB
    level. An encrypted value is not valid JSON, so storing one in a real
    jsonb column would be rejected outright.
    """

    description = (
        "JSON data encrypted using Fernet symmetric encryption (with key rotation)"
    )

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("default", dict)
        super().__init__(*args, **kwargs)
        keys = getattr(settings, "ENCRYPTED_FIELD_KEYS", None)
        if not keys:
            raise ValueError(
                "ENCRYPTED_FIELD_KEYS must be set in Django settings as a list of base64 keys."
            )
        self.fernets = [Fernet(k.encode() if isinstance(k, str) else k) for k in keys]
        self.primary_fernet = self.fernets[0]

    def get_prep_value(self, value):
        if value is None:
            return value
        json_str = json.dumps(value)
        encrypted = self.primary_fernet.encrypt(json_str.encode())
        return encrypted.decode()

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return self._decrypt(value)

    def to_python(self, value):
        if value is None or isinstance(value, (dict, list)):
            return value
        return self._decrypt(value)

    def _decrypt(self, value):
        for fernet in self.fernets:
            try:
                decrypted = fernet.decrypt(value.encode())
            except (InvalidToken, AttributeError):
                continue
            return json.loads(decrypted.decode())
        raise DecryptionError(
            "Unable to decrypt value with any configured ENCRYPTED_FIELD_KEYS."
        )
