# Installation

```bash
pip install django-integrations
```

## Settings

Add the app:

```python
INSTALLED_APPS = [
    ...,
    "django.contrib.sites",
    "integrations",
]

SITE_ID = 1
```

`django.contrib.sites` is required - the default tenant scope is Sites
(see [scopes-and-permissions.md](scopes-and-permissions.md)).

### `ENCRYPTED_FIELD_KEYS`

Required. A non-empty list of base64-encoded Fernet keys, used to
encrypt every stored secret. The first key is the primary key (used to
encrypt new/updated values); any additional keys are only used to
decrypt existing data, which is how key rotation works.

```python
ENCRYPTED_FIELD_KEYS = [
    "gAAAAA...",  # primary key - generate with Fernet.generate_key()
]
```

Generate a key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

If this setting is missing or contains an invalid key, `manage.py check`
reports it as `integrations.E006` rather than the app crashing on
import - see [encryption.md](encryption.md) for the full key-management
story, including rotation.

### Optional settings

- `INTEGRATIONS_SCOPE_RESOLVER` - dotted path to a callable resolving
  the current tenant scope from a request. Defaults to a Django-Sites
  -based resolver. See [scopes-and-permissions.md](scopes-and-permissions.md).
- `INTEGRATIONS_PERMISSION_POLICY` - dotted path to a permission policy
  class. Defaults to a policy backed by Django's own per-model
  permissions. See [scopes-and-permissions.md](scopes-and-permissions.md).

Both raise a clear `ImproperlyConfigured` error (and surface as
`integrations.E007`/`E008` in `manage.py check`) if set to something
unimportable.

## Migrate

```bash
python manage.py migrate
```

This creates the `Credential` table (`integration`, `config`, and
encrypted `secrets` columns, plus a small set of legacy columns kept for
backward compatibility with v1 - see
[migrating-from-v1.md](migrating-from-v1.md)).

## Try it

The `develop/` directory in this repository is a complete, runnable
Django project using the package, with two example integrations already
registered. From a checkout:

```bash
pip install -e ".[dev]"
cd develop
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Then visit `/` for the built-in list/configure UI, or `/api/v1/integrations/`
for the JSON API (both require logging in - superusers bypass the
permission checks described in
[scopes-and-permissions.md](scopes-and-permissions.md)).
