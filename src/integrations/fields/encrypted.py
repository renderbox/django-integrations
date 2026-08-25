import json

from cryptography.fernet import InvalidToken
from django.db import models

from integrations import conf
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

    def get_prep_value(self, value):
        if value is None:
            return value
        json_str = json.dumps(value)
        encrypted = conf.get_multi_fernet().encrypt(json_str.encode())
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
        try:
            decrypted = conf.get_multi_fernet().decrypt(value.encode())
        except InvalidToken:
            raise DecryptionError(
                "Unable to decrypt value with any configured ENCRYPTED_FIELD_KEYS."
            ) from None
        return json.loads(decrypted.decode())
