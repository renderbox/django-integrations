import base64
import os
import sys
import unittest

import django
from django.contrib.sites.models import Site
from django.db import connection, models
from django.test import TestCase, override_settings

from integrations.encrypted_fields import EncryptedTextField
from integrations.models import Credential


def setup_django():
    sys.path.insert(
        0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../develop"))
    )
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "develop.settings")
    django.setup()


setup_django()


class DummyModel(models.Model):
    secret = EncryptedTextField(null=True, blank=True)

    class Meta:
        app_label = "integrations"


class CredentialModelTest(TestCase):
    def setUp(self):
        # Use or get the default Site to avoid UNIQUE constraint errors
        self.site, _ = Site.objects.get_or_create(
            domain="example.com", defaults={"name": "Example"}
        )

    def test_create_credential(self):
        cred = Credential.objects.create(
            name="Test Integration",
            site=self.site,
            client_id="client123",
            client_url="https://api.example.com",
            public_key="public",
            private_key="private",
            attrs={"foo": "bar"},
        )
        self.assertEqual(cred.name, "Test Integration")
        self.assertEqual(cred.site, self.site)
        self.assertEqual(cred.client_id, "client123")
        self.assertEqual(cred.client_url, "https://api.example.com")
        self.assertEqual(cred.public_key, "public")
        self.assertEqual(cred.private_key, "private")
        self.assertEqual(cred.attrs, {"foo": "bar"})

    def test_blank_fields(self):
        cred = Credential.objects.create(site=self.site)
        self.assertIsNone(cred.name)
        self.assertIsNone(cred.client_id)
        self.assertIsNone(cred.client_url)
        self.assertIsNone(cred.public_key)
        self.assertIsNone(cred.private_key)
        self.assertEqual(cred.attrs, {})


@unittest.skipIf(
    connection.vendor == "sqlite",
    "Schema editor tests require PostgreSQL or another full DB backend.",
)
class EncryptedTextFieldTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.vendor == "sqlite":
            # Use a transaction to disable constraints for the schema editor
            with connection.cursor() as cursor:
                cursor.execute("PRAGMA foreign_keys = OFF;")
            connection.disable_constraint_checking()
            connection._constraints_disabled = True
        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(DummyModel)

    @classmethod
    def tearDownClass(cls):
        if connection.vendor == "sqlite":
            with connection.cursor() as cursor:
                cursor.execute("PRAGMA foreign_keys = OFF;")
            connection.disable_constraint_checking()
            connection._constraints_disabled = True
        with connection.schema_editor() as schema_editor:
            schema_editor.delete_model(DummyModel)
        super().tearDownClass()

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
        # Check raw value in DB is not plaintext
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT secret FROM {DummyModel._meta.db_table} WHERE id=%s", [obj.id]
            )
            encrypted = cursor.fetchone()[0]
        self.assertNotIn(value, encrypted)
