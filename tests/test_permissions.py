import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.sites.models import Site

from integrations.permissions import IntegrationPermissionPolicy
from integrations.scopes import IntegrationScope


@pytest.fixture
def site(db):
    return Site.objects.get_or_create(
        domain="example.com", defaults={"name": "Example"}
    )[0]


@pytest.fixture
def scope(site):
    return IntegrationScope(site=site)


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(username="alice", password="x")


def _grant(user, codename):
    """
    Grants the permission and returns a *fresh* user instance, since
    Django caches has_perm() results on the instance - reusing the same
    object after granting would just replay the stale (False) result.
    """
    permission = Permission.objects.get(
        content_type__app_label="integrations", codename=codename
    )
    user.user_permissions.add(permission)
    return get_user_model().objects.get(pk=user.pk)


class TestIntegrationPermissionPolicy:
    def test_can_view_requires_view_credential_permission(self, user, scope):
        policy = IntegrationPermissionPolicy()
        assert policy.can_view(user, scope, "zoom") is False
        user = _grant(user, "view_credential")
        assert policy.can_view(user, scope, "zoom") is True

    def test_can_configure_requires_change_credential_permission(self, user, scope):
        policy = IntegrationPermissionPolicy()
        assert policy.can_configure(user, scope, "zoom") is False
        user = _grant(user, "change_credential")
        assert policy.can_configure(user, scope, "zoom") is True

    def test_can_delete_requires_delete_credential_permission(self, user, scope):
        policy = IntegrationPermissionPolicy()
        assert policy.can_delete(user, scope, "zoom") is False
        user = _grant(user, "delete_credential")
        assert policy.can_delete(user, scope, "zoom") is True

    def test_can_test_connection_requires_change_credential_permission(
        self, user, scope
    ):
        policy = IntegrationPermissionPolicy()
        assert policy.can_test_connection(user, scope, "zoom") is False
        user = _grant(user, "change_credential")
        assert policy.can_test_connection(user, scope, "zoom") is True

    def test_superuser_can_do_everything(self, db, scope):
        superuser = get_user_model().objects.create_superuser(
            username="root", password="x", email="root@example.com"
        )
        policy = IntegrationPermissionPolicy()
        assert policy.can_view(superuser, scope, "zoom") is True
        assert policy.can_configure(superuser, scope, "zoom") is True
        assert policy.can_delete(superuser, scope, "zoom") is True
        assert policy.can_test_connection(superuser, scope, "zoom") is True
