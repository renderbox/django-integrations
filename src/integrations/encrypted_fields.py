from cryptography.fernet import InvalidToken
from django.db import models

from integrations import conf
from integrations.exceptions import DecryptionError


class EncryptedTextField(models.TextField):
    """
    Drop-in replacement for fernet_fields.EncryptedTextField with key rotation support.
    Set ENCRYPTED_FIELD_KEYS in settings as a list of base64 keys (like FERNET_KEYS).
    """

    description = "TextField that is encrypted using Fernet symmetric encryption (with key rotation)"

    def get_prep_value(self, value):
        if value is None:
            return value
        if isinstance(value, str):
            value = value.encode()
        encrypted = conf.get_multi_fernet().encrypt(value)
        return encrypted.decode()

    def from_db_value(self, value, expression, connection):
        """
        Always the raw column value from the database - i.e. always
        ciphertext. Unlike to_python(), a decrypt failure here is
        unambiguous: raise rather than silently return unusable ciphertext
        as though it were a real secret.
        """
        if value is None:
            return value
        try:
            return conf.get_multi_fernet().decrypt(value.encode()).decode()
        except InvalidToken:
            raise DecryptionError(
                "Unable to decrypt value with any configured ENCRYPTED_FIELD_KEYS."
            ) from None

    def to_python(self, value):
        """
        May receive either raw ciphertext (deserialization) or the
        instance's current Python value, which for a TextField is
        indistinguishable by type from ciphertext - both are plain str.
        The latter is the common case (e.g. ModelForm/full_clean() reading
        an already-decrypted value), so a decrypt failure here means "this
        was never ciphertext to begin with", not a real error - return it
        unchanged rather than raising.
        """
        if value is None:
            return value
        try:
            return conf.get_multi_fernet().decrypt(value.encode()).decode()
        except (InvalidToken, AttributeError):
            return value
