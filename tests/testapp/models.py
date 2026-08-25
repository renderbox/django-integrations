from django.db import models

from integrations.encrypted_fields import EncryptedTextField


class DummyModel(models.Model):
    secret = EncryptedTextField(null=True, blank=True)
