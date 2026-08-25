import base64
import os

from django.db import connection
from django.test import TestCase, override_settings

from tests.testapp.models import DummyModel


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
