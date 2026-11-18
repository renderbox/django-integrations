import base64
import json
import os

from cryptography.fernet import Fernet
from django.db import connection
from django.test import TestCase, override_settings

from integrations.exceptions import DecryptionError
from tests.testapp.models import DummyJSONModel


def _fresh_key():
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


class EncryptedJSONFieldTest(TestCase):
    def test_dict_round_trips(self):
        value = {"account_id": "acct-1", "nested": {"a": 1, "b": [1, 2, 3]}}
        obj = DummyJSONModel.objects.create(data=value)
        obj.refresh_from_db()
        self.assertEqual(obj.data, value)

    def test_default_is_empty_dict(self):
        obj = DummyJSONModel.objects.create()
        obj.refresh_from_db()
        self.assertEqual(obj.data, {})

    def test_stored_value_is_not_plain_json_and_leaks_no_plaintext(self):
        value = {"api_key": "super-secret-value"}
        obj = DummyJSONModel.objects.create(data=value)
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT data FROM {DummyJSONModel._meta.db_table} WHERE id=%s",
                [obj.id],
            )
            raw = cursor.fetchone()[0]

        self.assertNotIn("api_key", raw)
        self.assertNotIn("super-secret-value", raw)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(raw)

    def test_undecryptable_value_raises_decryption_error(self):
        obj = DummyJSONModel.objects.create(data={"a": 1})

        wrong_key_ciphertext = (
            Fernet(Fernet.generate_key())
            .encrypt(json.dumps({"a": 1}).encode())
            .decode()
        )
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {DummyJSONModel._meta.db_table} SET data = %s WHERE id = %s",
                [wrong_key_ciphertext, obj.id],
            )

        with self.assertRaises(DecryptionError):
            DummyJSONModel.objects.get(pk=obj.pk)

    def test_multi_key_rotation(self):
        key_a = _fresh_key()
        with override_settings(ENCRYPTED_FIELD_KEYS=[key_a]):
            obj = DummyJSONModel.objects.create(data={"account_id": "acct-1"})

        key_b = _fresh_key()
        with override_settings(ENCRYPTED_FIELD_KEYS=[key_b, key_a]):
            obj.refresh_from_db()
            self.assertEqual(obj.data, {"account_id": "acct-1"})
