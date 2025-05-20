from django.db import models
from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken


class EncryptedTextField(models.TextField):
    """
    Drop-in replacement for fernet_fields.EncryptedTextField with key rotation support.
    Set ENCRYPTED_FIELD_KEYS in settings as a list of base64 keys (like FERNET_KEYS).
    """

    description = "TextField that is encrypted using Fernet symmetric encryption (with key rotation)"

    def __init__(self, *args, **kwargs):
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
        if isinstance(value, str):
            value = value.encode()
        encrypted = self.primary_fernet.encrypt(value)
        return encrypted.decode()

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        for f in self.fernets:
            try:
                decrypted = f.decrypt(value.encode())
                return decrypted.decode()
            except (InvalidToken, AttributeError):
                continue
        return value

    def to_python(self, value):
        if value is None:
            return value
        for f in self.fernets:
            try:
                decrypted = f.decrypt(value.encode())
                return decrypted.decode()
            except (InvalidToken, AttributeError):
                continue
        return value
