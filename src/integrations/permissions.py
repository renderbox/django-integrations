from typing import Any, Protocol

from integrations.scopes import IntegrationScope


class _PermissionCheckable(Protocol):
    """
    Anything with Django's has_perm() contract - a real User, AnonymousUser,
    or a custom user model. Not AbstractBaseUser: has_perm() actually comes
    from PermissionsMixin, and AnonymousUser (a common request.user value
    for unauthenticated requests) implements it without inheriting from
    AbstractBaseUser at all.
    """

    def has_perm(self, perm: str, obj: Any = ...) -> bool: ...


class IntegrationPermissionPolicy:
    """
    Default INTEGRATIONS_PERMISSION_POLICY implementation.

    Pure boolean predicates - they don't raise PermissionDenied themselves.
    Deciding what to do with a False (403 response, redirect, hidden UI)
    belongs to whichever interface calls them (HTTP API, HTML views,
    admin). Uses Django's own auto-generated per-model permissions for
    Credential, so there's nothing extra to migrate.

    `scope`/`slug` are part of the signature so a custom policy can do
    object-level checks (e.g. via django-guardian) even though this
    default implementation ignores them for a simple blanket check.
    """

    def can_view(
        self, user: _PermissionCheckable, scope: IntegrationScope, slug: str
    ) -> bool:
        return user.has_perm("integrations.view_credential")

    def can_configure(
        self, user: _PermissionCheckable, scope: IntegrationScope, slug: str
    ) -> bool:
        return user.has_perm("integrations.change_credential")

    def can_delete(
        self, user: _PermissionCheckable, scope: IntegrationScope, slug: str
    ) -> bool:
        return user.has_perm("integrations.delete_credential")

    def can_test_connection(
        self, user: _PermissionCheckable, scope: IntegrationScope, slug: str
    ) -> bool:
        # No dedicated permission yet - nothing to test until Phase 11
        # introduces the test_connection capability.
        return user.has_perm("integrations.change_credential")
