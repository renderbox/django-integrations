from dataclasses import dataclass

from django.contrib.sites.models import Site
from django.http import HttpRequest


@dataclass(frozen=True)
class IntegrationScope:
    """
    Identifies the tenant boundary credential lookups are scoped to.

    A thin wrapper, not a replacement for Site at the persistence layer -
    Credential.site is a real FK (Phase 4) and stays so. This is the seam
    between "what identifies a tenant to calling code" and "what column
    the DB currently uses": if persistence ever needs to change, only
    this class and the persistence layer need to, not every call site.
    """

    site: Site


def default_scope_resolver(request: HttpRequest) -> IntegrationScope:
    """
    Default INTEGRATIONS_SCOPE_RESOLVER implementation. Uses Django's own
    current-site resolution (SITE_ID or host-matching, per how the host
    app has django.contrib.sites configured) rather than reinventing it.
    """
    return IntegrationScope(site=Site.objects.get_current(request))
