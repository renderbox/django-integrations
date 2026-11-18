import base64
import os

from cryptography.fernet import Fernet
from django.db import connection
from django.test import TestCase, override_settings

from integrations.exceptions import DecryptionError
from tests.testapp.models import DummyModel


def _fresh_key():
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


class EncryptedTextFieldTest(TestCase):
    @override_settings(
        ENCRYPTED_FIELD_KEYS=[base64.urlsafe_b64encode(os.urandom(32)).decode()]
    )
    def test_encryption_and_decryption(self):
        value = "super_secret_value"
        obj = DummyModel.objects.create(secret=value)
        obj.refresh_from_db()
        self.assertEqual(obj.secret, value)

    @override_settings(
        ENCRYPTED_FIELD_KEYS=[base64.urlsafe_b64encode(os.urandom(32)).decode()]
    )
    def test_none_value(self):
        obj = DummyModel.objects.create(secret=None)
        obj.refresh_from_db()
        self.assertIsNone(obj.secret)

    @override_settings(
        ENCRYPTED_FIELD_KEYS=[base64.urlsafe_b64encode(os.urandom(32)).decode()]
    )
    def test_encrypted_storage(self):
        value = "encrypt_me"
        obj = DummyModel.objects.create(secret=value)
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT secret FROM {DummyModel._meta.db_table} WHERE id=%s", [obj.id]
            )
            encrypted = cursor.fetchone()[0]
        self.assertNotIn(value, encrypted)

    @override_settings(ENCRYPTED_FIELD_KEYS=[_fresh_key()])
    def test_undecryptable_value_raises_decryption_error(self):
        obj = DummyModel.objects.create(secret="hello")

        wrong_key_ciphertext = Fernet(Fernet.generate_key()).encrypt(b"hello").decode()
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {DummyModel._meta.db_table} SET secret = %s WHERE id = %s",
                [wrong_key_ciphertext, obj.id],
            )

        with self.assertRaises(DecryptionError):
            DummyModel.objects.get(pk=obj.pk)

    def test_multi_key_rotation(self):
        key_a = _fresh_key()
        with override_settings(ENCRYPTED_FIELD_KEYS=[key_a]):
            obj = DummyModel.objects.create(secret="rotate-me")

        key_b = _fresh_key()
        with override_settings(ENCRYPTED_FIELD_KEYS=[key_b, key_a]):
            obj.refresh_from_db()
            self.assertEqual(obj.secret, "rotate-me")
