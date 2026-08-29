# Configuration and secrets

Every integration's stored data splits into two parts:

- **`config`** - non-secret values (account ids, base URLs, choices...).
  Stored as plain JSON. Safe to display as-is.
- **`secrets`** - values from `SecretField`s. Encrypted at rest
  (`EncryptedJSONField`) and **never returned** by any interface once
  stored - the API and HTML UI only ever say whether a secret is
  configured, never its value.

## The service layer

`integrations.services` is the shared layer the API, HTML views, and
admin all sit on top of - use it directly for any programmatic access
(e.g. a background task that needs a stored API key to make its own
outbound call):

```python
from integrations.scopes import IntegrationScope
from integrations import services

scope = IntegrationScope(site=some_site)

services.is_configured(scope, "zoom")            # -> bool
services.get_config(scope, "zoom")                # -> IntegrationConfig
services.save_config(scope, "zoom", {"account_id": "acct-1", "api_key": "..."})
services.delete_config(scope, "zoom")             # -> bool (was anything deleted)
```

`get_config()` always returns an `IntegrationConfig`, even when nothing
is stored yet (empty `config`/`secrets`) - no `None`-check needed just to
ask "what's configured." `IntegrationConfig.config` holds real,
decrypted, non-secret values; `.secrets` holds real, decrypted secret
values - this is the *internal* representation for code that actually
needs to use the credentials. Anything reaching an HTTP response should
go through `.to_api_metadata()` instead, which never includes a value,
only whether each secret is configured.

## Partial updates: omit, replace, or clear

`save_config()` takes a partial or full dict of field values and merges
it with whatever's already stored:

- **A field present in the dict** replaces the stored value.
- **A field omitted from the dict** preserves whatever's currently
  stored. This matters specifically for secrets: they're write-only, so
  a client can never resend a value it was never given back in the first
  place - omission is the *only* way to mean "leave this alone."
- **`CLEAR`** (secrets only) removes the stored value:

  ```python
  from integrations import CLEAR
  services.save_config(scope, "zoom", {"api_key": CLEAR})
  ```

  Clearing a *required* secret with no replacement value in the same
  call is rejected (`IntegrationValidationError`) - there'd be nothing
  left to satisfy "required."

The same call works for both first-time creation and later updates - if
nothing is stored yet, "preserve" has nothing to fall back on, so an
omitted required field raises exactly like a fresh, from-scratch
validation would.

Over HTTP, the JSON API represents `CLEAR` as an explicit `null` (see
[http-api.md](http-api.md)); the HTML UI represents it as a "Clear this
value" checkbox next to each optional secret field.
