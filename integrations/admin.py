from django.contrib import admin

from integrations.models import Credential



class CredentialAdmin(admin.ModelAdmin):
    list_display = ('name', 'site')
    search_fields = ('name', 'site')
    list_filter = ('site__domain', )


admin.site.register(Credential, CredentialAdmin)