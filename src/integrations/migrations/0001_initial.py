# Generated by Django 5.2.1 on 2025-05-20 19:12

import django.db.models.deletion
from django.db import migrations, models

import integrations.encrypted_fields
import integrations.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [
        migrations.CreateModel(
            name="Credential",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="date created"
                    ),
                ),
                (
                    "updated",
                    models.DateTimeField(auto_now=True, verbose_name="last updated"),
                ),
                (
                    "name",
                    models.CharField(
                        blank=True, max_length=80, null=True, verbose_name="name"
                    ),
                ),
                (
                    "client_id",
                    models.CharField(
                        blank=True, max_length=50, null=True, verbose_name="Client ID"
                    ),
                ),
                (
                    "client_url",
                    models.CharField(
                        blank=True, max_length=200, null=True, verbose_name="Client URL"
                    ),
                ),
                (
                    "public_key",
                    integrations.encrypted_fields.EncryptedTextField(
                        blank=True, null=True, verbose_name="Public Key"
                    ),
                ),
                (
                    "private_key",
                    integrations.encrypted_fields.EncryptedTextField(
                        blank=True, null=True, verbose_name="Private Key"
                    ),
                ),
                ("attrs", models.JSONField(blank=True, default=dict, null=True)),
                (
                    "site",
                    models.ForeignKey(
                        default=integrations.models.set_default_site_id,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="site",
                        to="sites.site",
                        verbose_name="Site",
                    ),
                ),
            ],
            options={
                "verbose_name": "Credential",
                "verbose_name_plural": "Credentials",
            },
        ),
    ]
