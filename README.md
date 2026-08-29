[![Python Tests](https://github.com/renderbox/django-integrations/actions/workflows/python-test.yml/badge.svg)](https://github.com/renderbox/django-integrations/actions/workflows/python-test.yml)

[![Publish Python 🐍 distribution 📦 to PyPI](https://github.com/renderbox/django-integrations/actions/workflows/python-publish.yml/badge.svg)](https://github.com/renderbox/django-integrations/actions/workflows/python-publish.yml)

# Django Integrations

Tools for defining, storing, validating, and managing multi-site
integrations - API keys, tokens, and their non-secret configuration -
without duplicating each provider's schema across models, forms, an API,
and an admin.

An `Integration` subclass is the single, canonical description of a
provider. Everything else - encrypted secret storage, tenant-scoped
retrieval, a generated edit form, JSON API metadata, secure partial
updates - is derived from it:

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

No stored secret is ever returned by any interface once saved.

## Installation

```bash
pip install django-integrations
```

```python
INSTALLED_APPS = [
    ...,
    "django.contrib.sites",
    "integrations",
]

SITE_ID = 1
ENCRYPTED_FIELD_KEYS = ["..."]  # see docs/encryption.md - required
```

Full documentation, including the required settings, the JSON API, the
built-in HTML UI, and connection testing, is in [`docs/`](docs/index.md).

## For developers

```bash
pip install -e ".[dev,test]"
pytest --cov=integrations tests
```

`develop/` is a complete, runnable Django project demonstrating the
package (see [`docs/installation.md`](docs/installation.md#try-it) for
how to run it) - its example integrations live in
[`develop/core/integrations.py`](develop/core/integrations.py).

See [`AGENTS.md`](AGENTS.md) and [`plan.md`](plan.md) for the
architecture and the project's own development plan.
