import pytest
from django.contrib.sites.models import Site
from django.test import RequestFactory

from integrations.scopes import IntegrationScope, default_scope_resolver


@pytest.fixture
def site(db):
    return Site.objects.get_or_create(
        domain="example.com", defaults={"name": "Example"}
    )[0]


class TestIntegrationScope:
    def test_wraps_a_site(self, site):
        scope = IntegrationScope(site=site)
        assert scope.site == site

    def test_equal_for_the_same_site(self, site):
        assert IntegrationScope(site=site) == IntegrationScope(site=site)

    def test_is_frozen(self, site):
        scope = IntegrationScope(site=site)
        with pytest.raises(AttributeError):
            scope.site = site  # type: ignore[misc]


class TestDefaultScopeResolver:
    def test_returns_a_scope_wrapping_the_current_site(self, site, settings):
        settings.SITE_ID = site.pk
        request = RequestFactory().get("/")
        scope = default_scope_resolver(request)
        assert isinstance(scope, IntegrationScope)
        assert scope.site == site
