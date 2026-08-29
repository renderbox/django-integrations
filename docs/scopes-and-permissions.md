# Tenant scope and authorization

These are deliberately separate concerns: resolving *which tenant* a
request belongs to doesn't say anything about whether *this user* is
allowed to manage that tenant's integrations.

## Scope

`IntegrationScope` identifies the tenant boundary every credential
lookup is scoped to - currently a thin wrapper around a `django.contrib
.sites.models.Site`:

```python
from integrations.scopes import IntegrationScope
scope = IntegrationScope(site=some_site)
```

Every function in `integrations.services` takes a `scope` as its first
argument, and every query it runs is filtered by it - there's no code
path that reads or writes a credential without going through a resolved
scope.

In an HTTP request, resolve the current scope with:

```python
from integrations import conf
scope = conf.resolve_scope(request)
```

By default this uses `Site.objects.get_current(request)` - Django's own
current-site resolution (`SITE_ID`, or host-matching if `SITE_ID` isn't
set). To scope by something other than Sites, set:

```python
INTEGRATIONS_SCOPE_RESOLVER = "yourapp.scopes.resolve_scope"
```

where the target is a callable `(request) -> IntegrationScope`. Note
that `Credential.site` is still a real foreign key to `Site` - a custom
resolver changes *how a scope gets resolved from a request*, not what
the database stores it against.

## Permissions

`IntegrationPermissionPolicy` (in `integrations.permissions`) has four
methods, each `(user, scope, slug) -> bool`:

- `can_view`
- `can_configure`
- `can_delete`
- `can_test_connection`

They're pure predicates - they don't raise or redirect themselves;
deciding what to do with `False` (403, redirect, hide a button) is up to
whichever interface calls them. Both the built-in API and HTML views
call the configured policy before every operation.

The default implementation checks Django's own auto-generated per-model
permissions for `Credential` - `integrations.view_credential`,
`.change_credential` (used for both configure and test-connection),
`.delete_credential`. Nothing extra to migrate; grant these the normal
way (`user.user_permissions.add(...)`, a group, or `is_superuser`, which
bypasses permission checks entirely).

To customize, subclass `IntegrationPermissionPolicy` (or write your own
class with the same four methods) and point to it:

```python
INTEGRATIONS_PERMISSION_POLICY = "yourapp.permissions.YourPolicy"
```

`scope`/`slug` are part of every method's signature specifically so a
custom policy can do object-level checks (e.g. via django-guardian) -
the default implementation ignores them for a simple blanket check.

Both `INTEGRATIONS_SCOPE_RESOLVER` and `INTEGRATIONS_PERMISSION_POLICY`
are validated by `manage.py check` (`integrations.E007`/`E008`) if set to
an unimportable dotted path.
