# Writing a provider package

For a real, specific provider meant to be reused across projects (rather
than an `Integration` subclass living in your own app), the intended
shape is a small, separate distribution: `django-integrations-stripe`,
`django-integrations-slack`, and so on. The core `django-integrations`
package deliberately doesn't accumulate every provider's SDK as a
dependency - keeping the base install to just Django + `cryptography` is
an explicit design goal, not an oversight.

## What such a package needs

At minimum:

```
django-integrations-yourprovider/
├── integrations_yourprovider/
│   ├── __init__.py
│   └── integration.py   # the Integration subclass(es)
├── pyproject.toml
└── README.md
```

```python
# integrations_yourprovider/integration.py
from integrations import Integration, register
from integrations.fields import SecretField, TextField

@register
class YourProviderIntegration(Integration):
    slug = "yourprovider"
    name = "Your Provider"
    fields = [
        TextField("account_id", label="Account ID", required=True),
        SecretField("api_key", label="API Key", required=True),
    ]
```

The consuming project just needs the package installed and something
that imports `integrations_yourprovider.integration` at startup (an
`AppConfig.ready()` if you also ship a small Django app; a plain import
in the host's own `ready()` otherwise) - see "Registering" in
[defining-integrations.md](defining-integrations.md).

## Guidelines

- **Don't build a deep inheritance hierarchy.** `Integration` is meant to
  stay a small base class plus declarative fields and capabilities, not
  a place for `OAuthIntegration -> RESTIntegration -> YourIntegration`.
  If you need provider-specific helper methods (e.g. `get_client()`),
  put them directly on your `Integration` subclass - they don't need to
  become part of every integration's interface.
- **Only add your actual provider SDK as a dependency of *your* package,
  never the core package.** That's the entire point of the split.
- **If you implement `test_connection()`,** read
  [connection-testing.md](connection-testing.md) first - in particular,
  use a timeout for any outbound call, and never put a secret value into
  a message you raise or return.
- **Don't couple your field definitions to a database column name.**
  `SecretField("api_key")` describes the provider's own concept; it
  should never need to know or care what a legacy model might have
  called the equivalent value.
- **Pick a real slug and keep it stable.** It's the identifier stored in
  `Credential.integration` and used throughout the API/URLs - renaming
  it later is a breaking change for anyone who configured it.
