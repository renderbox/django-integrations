# Defining an integration

An integration is a plain `Integration` subclass:

```python
from integrations import Integration, register
from integrations.fields import SecretField, TextField

@register
class ZoomIntegration(Integration):
    slug = "zoom"
    name = "Zoom"
    description = "Zoom video conferencing."
    fields = [
        TextField("account_id", label="Account ID", required=True),
        SecretField("api_key", label="API Key", required=True),
    ]
```

- `slug` - a stable identifier (lowercase letters, digits, `-`, `_`).
  Used as the URL segment, the API resource id, and the value stored in
  `Credential.integration`.
- `name` / `description` - human-readable, shown in the UI and API.
- `fields` - the field definitions below.
- `capabilities` - see [connection-testing.md](connection-testing.md).

`@register` (from `integrations`) adds the class to the registry so it
can be looked up by slug - see "Registering" below.

## Fields

All fields live in `integrations.fields`. Every field takes `name` plus:

| kwarg | default | meaning |
|---|---|---|
| `label` | title-cased `name` | shown in forms/API metadata |
| `required` | `True` | see per-field notes below |
| `help_text` | `""` | shown under the form field |
| `default` | `None` | used when the field is optional and omitted |

| Field | Extra kwargs | Notes |
|---|---|---|
| `TextField` | - | plain string |
| `SecretField` | - | a `TextField` that's encrypted at rest and never returned by any interface once stored - see [configuration-and-secrets.md](configuration-and-secrets.md) |
| `URLField` | - | validated as a URL |
| `ChoiceField` | `choices` (required) - a list of values, or `(value, label)` pairs | |
| `BooleanField` | - | `required` defaults to `False` (unchecked is a valid value) |
| `IntegerField` | `min_value`, `max_value` | |

A field's `name` is the key it's stored under in `config` (non-secret
fields) or `secrets` (secret fields) - it describes the provider's
concept, not a database column. Field names must be unique within one
integration (enforced immediately, at class-definition time).

## Cross-field validation

Override `validate()` for rules that involve more than one field. It
runs only after every individual field has already passed its own
validation:

```python
from integrations.exceptions import IntegrationValidationError

class ZoomIntegration(Integration):
    ...
    @classmethod
    def validate(cls, config, secrets):
        if config.get("mode") == "sandbox" and not config.get("account_id", "").startswith("sandbox-"):
            raise IntegrationValidationError({
                "account_id": ["Sandbox mode requires a sandbox- prefixed account id."]
            })
```

Do not make external network calls here - that's what
[connection-testing.md](connection-testing.md) is for. Validation must
stay deterministic and local.

## Registering

`@register` is the normal way - it's a plain decorator, so registration
happens as an ordinary import side effect. Put your `Integration`
subclasses somewhere that reliably gets imported at startup, and call
`registry.register()` there - a Django app's `AppConfig.ready()` is the
conventional place (the same pattern Django itself uses for signal
registration):

```python
# yourapp/apps.py
class YourAppConfig(AppConfig):
    def ready(self):
        from yourapp import integrations  # noqa: F401 - registers via @register
```

The package does not scan `INSTALLED_APPS` looking for integration
modules - that kind of import-discovery magic is deliberately avoided
(see AGENTS.md if you're curious why).

Duplicate slugs are rejected immediately, at registration time
(`DuplicateIntegrationError`), except that re-registering the exact same
class is a harmless no-op (so autoreload/module re-import doesn't break).
