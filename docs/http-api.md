# HTTP API

Plain Django views (no DRF dependency). Mount at whatever prefix your
project wants:

```python
# yourproject/urls.py
urlpatterns = [
    path("api/", include("integrations.api.urls")),
]
```

`v1` is baked into the package's own URLs (`api/v1/integrations/...`) -
that's this API's own contract version, independent of the package's
release version. The machine-readable OpenAPI 3.0.3 document describing
all of this is served at `v1/openapi.json` (no authentication required,
same as any other API documentation).

| Method | Path | |
|---|---|---|
| GET | `v1/integrations/` | list integrations visible to the caller |
| GET | `v1/integrations/{slug}/` | one integration's definition |
| GET | `v1/integrations/{slug}/configuration/` | current stored configuration |
| PUT / PATCH | `v1/integrations/{slug}/configuration/` | create or update |
| DELETE | `v1/integrations/{slug}/configuration/` | remove the configuration |
| POST | `v1/integrations/{slug}/test/` | run `test_connection()` |

All of them require an authenticated session (`401` otherwise) and check
the configured permission policy (`403` otherwise) - see
[scopes-and-permissions.md](scopes-and-permissions.md). CSRF protection
is Django's own default for session-authenticated requests; nothing in
the package exempts it.

## List / detail

```json
{
  "slug": "zoom",
  "name": "Zoom",
  "description": "Zoom video conferencing.",
  "fields": [
    {"name": "account_id", "type": "text", "label": "Account ID", "required": true, "help_text": ""},
    {"name": "api_key", "type": "secret", "label": "API Key", "required": true, "help_text": ""}
  ],
  "configured": true,
  "capabilities": []
}
```

Field entries here describe the *schema* - never a value, and no
per-field `configured` flag (that's the configuration endpoint, below).

## Configuration

```json
{
  "integration": "zoom",
  "configured": true,
  "fields": [
    {"name": "account_id", "type": "text", "label": "Account ID", "required": true, "help_text": "", "value": "acct-1"},
    {"name": "api_key", "type": "secret", "label": "API Key", "required": true, "help_text": "", "configured": true}
  ]
}
```

Non-secret fields include their real `value`. Secret fields only ever
show `configured` - never a value.

**PUT and PATCH are intentionally identical.** Both apply the
partial-update semantics described in
[configuration-and-secrets.md](configuration-and-secrets.md): a field
omitted from the request body preserves its stored value. True
RFC 9110 PUT semantics (resend the complete representation) aren't
achievable here - secret fields are write-only, so a client can never
reconstruct one to resend in the first place.

**An explicit JSON `null` clears a secret** (RFC 7396 JSON Merge Patch
semantics):

```json
PATCH .../configuration/
{"webhook_secret": null}
```

`null` on a non-secret field is a validation error (`422`) - only
secrets can be cleared this way.

`DELETE` returns `204` whether or not anything was actually stored
(idempotent).

## Errors

Every error is [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457)
Problem Details (`application/problem+json`):

```json
{
  "type": "about:blank",
  "title": "Validation failed",
  "status": 422,
  "errors": {
    "api_key": ["This field is required."]
  }
}
```

| Status | When |
|---|---|
| 400 | request body isn't valid JSON, or isn't a JSON object |
| 401 | not authenticated |
| 403 | authenticated, but the permission policy said no |
| 404 | unknown slug, or (for `/test/`) the integration doesn't declare `test_connection` |
| 405 | unsupported HTTP method |
| 422 | validation failed - `errors` maps field name to a list of messages, plus an optional `__all__` bucket for cross-field errors |

## Connection test

```json
POST .../test/
-> 200 {"success": true, "message": "Connected!"}
```

Always `200` if the request itself was valid - `success`/`message`
describe the *test's own outcome*, not a transport error. See
[connection-testing.md](connection-testing.md).

No CORS handling is added by the package - that's the host application's
decision (`django-cors-headers` or similar), consistent with not baking
in a permissive default.
