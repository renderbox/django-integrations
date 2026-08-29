# Connection testing

An integration can optionally support verifying connectivity/credentials
against the real provider. Declare it and implement it:

```python
from integrations import Integration
from integrations.capabilities import TEST_CONNECTION, ConnectionTestResult

class ZoomIntegration(Integration):
    ...
    capabilities = (TEST_CONNECTION,)

    @classmethod
    def test_connection(cls, config):
        # config.secrets holds real, decrypted values here - you need
        # them to actually authenticate.
        ...
        return ConnectionTestResult(success=True, message="Connected!")
```

`capabilities` is how every interface *discovers* whether an integration
supports this, without guessing - it's in the API's list/detail
responses, and it's what gates whether the HTML detail page shows a
"Test Connection" button. If you don't declare `"test_connection"`,
nothing tries to call `test_connection()` - and the base implementation
raises `NotImplementedError` if something does anyway, so a
declared-but-unimplemented capability fails loudly rather than pretending
to work.

`capabilities` is deliberately small - `test_connection` is the only one
implemented right now. `webhooks` and `oauth` are plausible future
additions, not built speculatively ahead of an actual need.

## What the service layer does for you

Call it through `integrations.services.test_connection(scope, slug)`,
not `Integration.test_connection()` directly - the service function is
where the actual safety net lives:

- Raises `CapabilityNotSupportedError` if the integration doesn't
  declare the capability.
- Returns `ConnectionTestResult(success=False, "Not configured yet.")`
  without calling your code at all if nothing is stored yet - there's
  nothing to test.
- Catches *any* exception your `test_connection()` raises, logs it in
  full server-side (`logging.getLogger("integrations.services.credentials")`)
  for operator debugging, and returns a generic failure result to the
  caller. The HTTP response never sees exception internals.

That last point is a real but partial guarantee, not a complete one: if
your `test_connection()` embeds a secret in a message it raises, that
message *does* reach the server log - Python has no way to detect "is
this string a credential" and scrub it. So:

- **Never embed a secret value in an exception's message.** Reference
  `config.config` (safe) freely; never put `config.secrets` values into
  a string you raise or return.
- **Use a timeout for any outbound call.** The package has no HTTP
  client dependency of its own (only Django + `cryptography`), so this
  is on your implementation - `develop/core/integrations.py`'s
  `ExampleCRM.test_connection()` shows a real, dependency-free pattern
  using `urllib.request` with a timeout.
- **Catch your own provider/network exceptions and return a failure
  result** rather than letting them propagate where possible - it's
  friendlier than relying on the generic fallback message, though the
  fallback exists specifically so an unexpected bug doesn't turn into a
  500 or a secret leak.
