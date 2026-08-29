"""
Regression test for a real bug found while verifying Phase 12's demo
project: integrations.urls (HTML) and integrations.api.urls used to share
identical route names (integration-list, integration-detail, ...). Both
are meant to be mounted simultaneously by a host app, and Django's
reverse() resolves a same-named pattern from whichever urlconf was
registered last - so which one `redirect("integration-detail", ...)`
actually reached depended on mount order. It happened to work in
tests/urls.py's mount order and broke in develop/'s (which mounts them in
the opposite order) - passing here only proves the names are distinct
enough not to depend on order at all.
"""

from django.urls import reverse


class TestUrlNamesDoNotCollide:
    def test_html_and_api_detail_names_resolve_to_different_urls(self):
        html_url = reverse("integration-detail", kwargs={"slug": "widget"})
        api_url = reverse("api-integration-detail", kwargs={"slug": "widget"})
        assert html_url == "/integrations/widget/"
        assert api_url == "/api/v1/integrations/widget/"
        assert html_url != api_url

    def test_html_and_api_list_names_resolve_to_different_urls(self):
        html_url = reverse("integration-list")
        api_url = reverse("api-integration-list")
        assert html_url == "/integrations/"
        assert api_url == "/api/v1/integrations/"
        assert html_url != api_url
