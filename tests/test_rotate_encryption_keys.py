import base64
import os

from django.contrib.sites.models import Site
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings

from integrations.models import Credential
from tests.testapp.models import DummyJSONModel, DummyModel


def _fresh_key():
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


def _raw_column(table, column, pk):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {column} FROM {table} WHERE id=%s", [pk])
        return cursor.fetchone()[0]


class RotateEncryptionKeysCommandTest(TestCase):
    def setUp(self):
        self.site, _ = Site.objects.get_or_create(
            domain="example.com", defaults={"name": "Example"}
        )

    def test_rotates_all_encrypted_fields_across_models(self):
        key_a = _fresh_key()
        with override_settings(ENCRYPTED_FIELD_KEYS=[key_a]):
            cred = Credential.objects.create(
                site=self.site,
                integration="zoom",
                private_key="private-value",
                secrets={"api_key": "sekrit"},
            )
            text_obj = DummyModel.objects.create(secret="hello")
            json_obj = DummyJSONModel.objects.create(data={"a": 1})

        raw_before = {
            "cred_private_key": _raw_column(
                Credential._meta.db_table, "private_key", cred.pk
            ),
            "cred_secrets": _raw_column(Credential._meta.db_table, "secrets", cred.pk),
            "text": _raw_column(DummyModel._meta.db_table, "secret", text_obj.pk),
            "json": _raw_column(DummyJSONModel._meta.db_table, "data", json_obj.pk),
        }

        key_b = _fresh_key()
        with override_settings(ENCRYPTED_FIELD_KEYS=[key_b, key_a]):
            call_command("rotate_encryption_keys")

            raw_after = {
                "cred_private_key": _raw_column(
                    Credential._meta.db_table, "private_key", cred.pk
                ),
                "cred_secrets": _raw_column(
                    Credential._meta.db_table, "secrets", cred.pk
                ),
                "text": _raw_column(DummyModel._meta.db_table, "secret", text_obj.pk),
                "json": _raw_column(DummyJSONModel._meta.db_table, "data", json_obj.pk),
            }

            for key in raw_before:
                self.assertNotEqual(raw_before[key], raw_after[key], key)

            cred.refresh_from_db()
            text_obj.refresh_from_db()
            json_obj.refresh_from_db()
            self.assertEqual(cred.private_key, "private-value")
            self.assertEqual(cred.secrets, {"api_key": "sekrit"})
            self.assertEqual(text_obj.secret, "hello")
            self.assertEqual(json_obj.data, {"a": 1})

        # Old key fully retired: everything must still read correctly,
        # proving the rewrite really happened with the new primary key
        # rather than being a no-op.
        with override_settings(ENCRYPTED_FIELD_KEYS=[key_b]):
            cred.refresh_from_db()
            text_obj.refresh_from_db()
            json_obj.refresh_from_db()
            self.assertEqual(cred.private_key, "private-value")
            self.assertEqual(cred.secrets, {"api_key": "sekrit"})
            self.assertEqual(text_obj.secret, "hello")
            self.assertEqual(json_obj.data, {"a": 1})

    def test_dry_run_makes_no_changes(self):
        key_a = _fresh_key()
        with override_settings(ENCRYPTED_FIELD_KEYS=[key_a]):
            text_obj = DummyModel.objects.create(secret="hello")

        raw_before = _raw_column(DummyModel._meta.db_table, "secret", text_obj.pk)

        key_b = _fresh_key()
        with override_settings(ENCRYPTED_FIELD_KEYS=[key_b, key_a]):
            call_command("rotate_encryption_keys", dry_run=True)
            raw_after = _raw_column(DummyModel._meta.db_table, "secret", text_obj.pk)

        self.assertEqual(raw_before, raw_after)
