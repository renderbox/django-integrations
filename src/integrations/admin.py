from django.contrib import admin

from integrations import registry
from integrations.exceptions import IntegrationNotRegisteredError
from integrations.models import Credential


class CredentialAdmin(admin.ModelAdmin):
    list_display = ("name", "integration", "site", "integration_status")
    list_filter = ("site__domain", "integration")
    search_fields = ("name", "site__domain", "integration")
    # Excluded, not just read-only: a read-only field still renders its
    # value into the DOM via Django's default widget, which is exactly
    # the exposure to avoid. This covers both the new `secrets` field and
    # the legacy EncryptedTextFields, which decrypt on instance access and
    # were never previously protected here.
    exclude = ("secrets", "public_key", "private_key")
    readonly_fields = ("secrets_summary",)

    def get_readonly_fields(self, request, obj=None):
        fields = list(self.readonly_fields)
        if obj is not None:
            # Locked after creation so an operator can't silently retarget
            # a row's config to a different integration's schema, or break
            # the (site, integration) uniqueness invariant. Still editable
            # at creation time - exactly as unvalidated as `attrs` always
            # has been; this doesn't newly validate it.
            fields.extend(["integration", "config"])
        return fields

    @admin.display(description="Status")
    def integration_status(self, obj):
        if not obj.integration:
            return "—"
        try:
            registry.get(obj.integration)
        except IntegrationNotRegisteredError:
            return "Unregistered"
        return "Registered"

    @admin.display(description="Secrets")
    def secrets_summary(self, obj):
        parts = []

        integration_cls = None
        if obj.integration:
            try:
                integration_cls = registry.get(obj.integration)
            except IntegrationNotRegisteredError:
                integration_cls = None

        secrets = obj.secrets or {}
        if integration_cls is not None:
            for field in integration_cls.secret_fields():
                configured = field.name in secrets
                parts.append(
                    f"{field.label}: {'configured' if configured else 'not set'}"
                )
        else:
            parts.extend(f"{name}: configured" for name in secrets)

        if obj.public_key:
            parts.append("Legacy public_key: configured")
        if obj.private_key:
            parts.append("Legacy private_key: configured")

        return ", ".join(parts) if parts else "No secrets stored"


admin.site.register(Credential, CredentialAdmin)
