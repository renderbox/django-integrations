# django-integrations

A reusable Django app for defining, storing, validating, and managing
third-party service integrations (API keys, tokens, and their
non-secret configuration) on a per-tenant basis.

The core idea: an `Integration` subclass is the single, canonical
description of a provider - its configuration fields, which of those
are secret, and any cross-field validation. Persistence, the HTTP API,
the built-in Django views/forms, and the admin all consume that one
definition instead of each reimplementing provider-specific logic.

```python
from integrations import Integration, register
from integrations.fields import SecretField, TextField

@register
class ZoomIntegration(Integration):
    slug = "zoom"
    name = "Zoom"
    fields = [
        TextField("account_id", label="Account ID", required=True),
        SecretField("api_key", label="API Key", required=True),
    ]
```

That's enough to get validated configuration storage, encrypted secret
storage, tenant-scoped retrieval, a generated edit form, JSON API
metadata, and secure partial updates - see
[defining-integrations.md](defining-integrations.md) for the full
picture.

## Where to start

- **New to the package?** Read [installation.md](installation.md), then
  [defining-integrations.md](defining-integrations.md).
- **Want a working example?** `develop/` in this repository is a real,
  runnable Django project with two example integrations
  (`develop/core/integrations.py`) wired up to both the built-in HTML UI
  and the JSON API. Run it with `develop/manage.py runserver` after
  following [installation.md](installation.md).
- **Migrating an app from v1?** See
  [migrating-from-v1.md](migrating-from-v1.md).
- **Writing a real provider package** (e.g. `django-integrations-stripe`)?
  See [writing-provider-packages.md](writing-provider-packages.md).

## Reference

- [installation.md](installation.md) - installing the package, required
  settings, running migrations.
- [defining-integrations.md](defining-integrations.md) - `Integration`,
  fields, registering, capabilities.
- [configuration-and-secrets.md](configuration-and-secrets.md) - how
  config and secrets are validated, stored, and updated.
- [scopes-and-permissions.md](scopes-and-permissions.md) - tenant
  isolation and authorization.
- [http-api.md](http-api.md) - the JSON API.
- [html-ui.md](html-ui.md) - the built-in server-rendered UI.
- [connection-testing.md](connection-testing.md) - the `test_connection`
  capability.
- [encryption.md](encryption.md) - `ENCRYPTED_FIELD_KEYS` and key
  rotation.
- [migrating-from-v1.md](migrating-from-v1.md) - upgrading from the
  legacy `Credential` columns.
- [writing-provider-packages.md](writing-provider-packages.md) -
  packaging a real integration for distribution.
