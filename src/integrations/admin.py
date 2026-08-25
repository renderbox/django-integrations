from django.contrib import admin

from integrations.models import Credential


class CredentialAdmin(admin.ModelAdmin):
    list_display = ("name", "site")
    search_fields = ("name", "site")
    list_filter = ("site__domain",)
    # Stopgap until Phase 10's full admin treatment: never auto-render
    # secrets as a plain editable field in the admin form.
    exclude = ("secrets",)


admin.site.register(Credential, CredentialAdmin)
