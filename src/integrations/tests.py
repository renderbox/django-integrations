from django.contrib.sites.models import Site
from django.test import TestCase

from integrations.models import Credential


class CredentialModelTest(TestCase):
    def setUp(self):
        self.site = Site.objects.create(domain="example.com", name="Example")

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
