from django.db import models

from integrations.encrypted_fields import EncryptedTextField
from integrations.fields.encrypted import EncryptedJSONField


class DummyModel(models.Model):
    secret = EncryptedTextField(null=True, blank=True)


class DummyJSONModel(models.Model):
    data = EncryptedJSONField(default=dict)
