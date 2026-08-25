from django.contrib.sites.models import Site
from django.db import IntegrityError, connection, transaction
from django.test import TestCase

from integrations.models import Credential


class CredentialModelTest(TestCase):
    def setUp(self):
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
        self.assertIsNone(cred.integration)
        self.assertEqual(cred.config, {})
        self.assertEqual(cred.secrets, {})


class CredentialV2FieldsTest(TestCase):
    def setUp(self):
        self.site, _ = Site.objects.get_or_create(
            domain="example.com", defaults={"name": "Example"}
        )

    def test_config_and_secrets_round_trip(self):
        cred = Credential.objects.create(
            site=self.site,
            integration="zoom",
            config={"account_id": "acct-1"},
            secrets={"api_key": "sekrit"},
        )
        cred.refresh_from_db()
        self.assertEqual(cred.config, {"account_id": "acct-1"})
        self.assertEqual(cred.secrets, {"api_key": "sekrit"})

    def test_config_is_stored_as_plain_json_unlike_secrets(self):
        cred = Credential.objects.create(
            site=self.site,
            integration="zoom",
            config={"account_id": "acct-1"},
            secrets={"api_key": "sekrit"},
        )
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT config, secrets FROM {Credential._meta.db_table} WHERE id=%s",
                [cred.id],
            )
            raw_config, raw_secrets = cursor.fetchone()

        self.assertIn("account_id", raw_config)
        self.assertNotIn("api_key", raw_secrets)
        self.assertNotIn("sekrit", raw_secrets)

    def test_duplicate_site_integration_raises_integrity_error(self):
        Credential.objects.create(site=self.site, integration="zoom")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Credential.objects.create(site=self.site, integration="zoom")

    def test_multiple_null_integration_rows_allowed_per_site(self):
        # Legacy-style rows (no integration slug) must be able to coexist,
        # matching develop/core's Zoom/Vouchery/AuthorizeNet forms writing
        # to the same table with no way to disambiguate providers.
        Credential.objects.create(site=self.site, name="Zoom (legacy)")
        Credential.objects.create(site=self.site, name="Vouchery (legacy)")
        self.assertEqual(
            Credential.objects.filter(site=self.site, integration__isnull=True).count(),
            2,
        )

    def test_site_related_name_is_credentials(self):
        cred = Credential.objects.create(site=self.site, integration="zoom")
        self.assertIn(cred, self.site.credentials.all())
