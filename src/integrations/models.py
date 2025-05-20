from django.contrib.sites.models import Site
from django.db import models
from django.utils.translation import gettext_lazy as _
from fernet_fields import EncryptedTextField


def set_default_site_id():
    return Site.objects.get_current()


#######################################
# ABSTRACT MODELS
class CreateUpdateModelBase(models.Model):
    '''
    This is a shared models base that provides created & updated timestamp fields
    '''
    created = models.DateTimeField("date created", auto_now_add=True)
    updated = models.DateTimeField("last updated", auto_now=True)

    class Meta:
        abstract = True

class Credential(CreateUpdateModelBase):
    """
    Model to hold specified values for different integrations, the only required field is the site.
    The logic behind the fields is left to the Integration Class defined by the develoepr
    """
    name = models.CharField(verbose_name=_("name"), blank=True, null=True, max_length=80)
    site = models.ForeignKey(Site, verbose_name=_("Site"), on_delete=models.CASCADE, default=set_default_site_id, related_name="site")
    client_id = models.CharField(verbose_name=_("Client ID"), blank=True, null=True, max_length=50)
    client_url = models.CharField(verbose_name=_("Client URL"), blank=True, null=True, max_length=200)
    public_key = EncryptedTextField(null=True, blank=True, verbose_name=_("Public Key"))
    private_key = EncryptedTextField(null=True, blank=True, verbose_name=_("Private Key"))
    attrs = models.JSONField(null=True, blank=True, default=dict)

    objects = models.Manager()

    class Meta:
        verbose_name = "Credential"
        verbose_name_plural = "Credentials"