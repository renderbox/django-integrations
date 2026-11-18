# django-integrations OAuth Connections Plan (v2.1)

## Status

Approved 2026-11-18 by the project owner ("Both plans look good and are ready to go").

Raised by `blackmesa-social` (plan 001 and its follow-ups): connecting a platform's social media accounts (YouTube,
Instagram, Facebook, TikTok, X) by signing in, instead of copying API keys. Most of those providers offer no key-only
access, and publishing needs a write token per account.

`plans/000-v2.md` (v2) lists a "generic OAuth flow framework" as deferred "unless required by a concrete integration" and
`oauth` as a future capability. This plan is that concrete requirement. It follows `AGENTS.md` and `plans/000-v2.md` in
everything else.

## Baseline

| Repository | Branch | Commit | Evaluated |
|---|---|---|---|
| django-integrations | `develop` | `8571812164e26f05abe0f205dcd2ffc7948f762d` (`manually setting to v2.0.0`) | 2026-11-18 |

- `pyproject.toml` says 2.0.0; there is no `v2.0.0` tag and PyPI's newest release is 0.5.0.
- `Django>=5.2,<6.1`; CI tests Python 3.10–3.13 against Django 5.2 (and 6.0).
- The working tree has the owner's uncommitted `docs/examples/` and
  `tests/test_migrate_legacy_credentials_example.py`. This plan doesn't touch them.

## Owner decisions (2026-11-18)

1. **Add OAuth sign-in** to django-integrations, as an `oauth` capability, so any consuming package can connect
   provider accounts without copying keys.
2. **Change AGENTS.md rule 9 for connections only.** A `Credential` stays one per (site, integration): it holds the
   OAuth *client* (client ID and secret, entered once per site). A new `Connection` holds one *authorised provider
   account*, and a site may have several per integration (two YouTube channels, say), one per provider account.

## Findings

- **The OAuth client fits the existing model.** Client ID and secret are ordinary fields (`TextField`,
  `SecretField`) on the integration's `Credential`; nothing changes there.
- **Tokens don't.** They are per provider account, rotate on refresh, expire, and can be revoked by the account's
  owner at any time. They need their own encrypted rows, a status, and a refresh path that two workers can't break.
- **No HTTP client in core.** The base install is Django and `cryptography` only. The token exchange is a small
  form-encoded POST, which the standard library (`urllib.request`, with a timeout) can do; no new dependency.
- **Provider quirks to verify against current docs before relying on them**, not from memory:
  - Google issues a refresh token only with `access_type=offline` (and, to get one again, `prompt=consent`).
  - Google apps with sensitive scopes such as `youtube.readonly` are, while unverified ("Testing"), limited to test
    users, and their refresh tokens expire after 7 days. Production needs Google's app verification.
  - Meta (Instagram, Facebook) uses long-lived tokens exchanged and extended differently from a standard refresh;
    TikTok and X use refresh tokens with PKCE.
  - So the core handles standard OAuth 2.0 authorization code + PKCE + refresh, and leaves room for a provider to
    override the exchange or refresh on its own `Integration` subclass (rule 8: a method, not a hierarchy).

## Target shape

### Defining an OAuth integration

```python
from integrations import Integration, OAuth, register
from integrations.capabilities import OAUTH
from integrations.fields import SecretField, TextField


@register
class GoogleYouTubeIntegration(Integration):
    slug = "social-youtube"
    name = "YouTube"
    capabilities = (OAUTH,)
    fields = [
        # An integration may offer key access, sign-in, or both: the key covers public data for accounts that
        # aren't connected; clean() requires at least one of the two to be configured.
        SecretField("api_key", label="API key", required=False),
        TextField("client_id", label="Client ID", required=False),
        SecretField("client_secret", label="Client secret", required=False),
    ]
    oauth = OAuth(
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        revoke_url="https://oauth2.googleapis.com/revoke",
        scopes=["https://www.googleapis.com/auth/youtube.readonly"],
        authorize_params={"access_type": "offline", "prompt": "consent"},
    )

    def fetch_account(self, access_token: str) -> "ProviderAccount":
        """Who did we just connect? Provider-specific; required for OAUTH."""
        ...
```

- `OAuth` is a frozen dataclass (URLs, default scopes, extra authorise parameters, PKCE on by default, client
  authentication method). No `OAuthIntegration` base class.
- `fetch_account(access_token)` returns `ProviderAccount(account_id, display_name, extra)`; `account_id` is the
  provider's stable ID.
- Optional overrides on the subclass: `exchange_code(...)` and `refresh(...)`, for providers that differ from the
  standard (Meta).
- System checks: an `OAUTH` integration without `oauth`, without `fetch_account`, or without `client_id` /
  `client_secret` fields is an error. The fields may be optional, so an integration can also be used with other
  credentials only (an API key); `begin_authorization` then refuses with `oauth_client_not_configured`.

### Models

- **`Connection`**: `site`, `integration` (slug), `account_id`, `display_name`, `extra` (non-secret JSON), `tokens`
  (`EncryptedJSONField`: access token, refresh token), `scopes` (granted), `access_expires_at`, `status` (`active`,
  `needs_reauthorization`, `revoked`), `token_version` (for safe refresh), `connected_by` (user, nullable),
  `created`, `updated`. Unique per (site, integration, account_id). Reconnecting the same account updates its row.
- **`AuthorizationRequest`**: a pending sign-in. `state` (stored hashed), `code_verifier` (encrypted), `site`,
  `integration`, `user`, `scopes`, `return_to`, `expires_at` (10 minutes), `used_at`. Single use; expired rows are
  removed by a management command and opportunistically.

### Services (`integrations.services.oauth`)

- `begin_authorization(scope, slug, user, *, scopes=None, return_to=None, reconnect=None) -> str`: checks the
  client is configured, creates the `AuthorizationRequest`, returns the provider's authorise URL. `reconnect` (a
  `Connection`) signs an existing account in again: it records the connection on the request and passes the
  provider's account hint where supported (Google's `login_hint`).
- `complete_authorization(request, slug) -> Connection`: validates state (exists, unused, unexpired, same user, same
  site), marks it used, exchanges the code (outside any transaction, with a timeout), calls `fetch_account`, then
  saves the connection in one short transaction. On a reconnect, a different account signing in is refused
  (`account_mismatch`) and the existing connection is left as it was; the same account replaces the tokens and scopes
  and returns the connection to `active`.
- `get_access_token(connection) -> str`: returns a valid token, refreshing first when it expires within a margin.
  Refresh is compare-and-swap on `token_version`: whoever loses the race rereads the winner's token instead of
  refreshing again (a rotated refresh token would otherwise be spent twice). `invalid_grant` marks the connection
  `needs_reauthorization`.
- `list_connections(scope, slug)`, `get_connection(scope, slug, id)`, and
  `disconnect(scope, slug, id, *, revoke=True)`: revokes at the provider when it can, then deletes the row. A failed
  revocation is reported, not hidden; the row is still deleted.
- Every function takes the scope first and filters by it, like `services.credentials`.
- Signal `connection_status_changed(connection, old_status, new_status)`, sent after the change is saved, so a host
  or consuming package can tell someone a connection needs reconnecting (an email, a dashboard warning). The package
  sends no email itself.

### When people have to act

Access tokens are refreshed automatically; nobody updates a token by hand. People act only when the provider stops
honouring the refresh token: access removed by the account owner, an unverified Google app's 7-day expiry, new
scopes needed, or a token dropped by the provider (unused for months, or too many issued). The connection becomes
`needs_reauthorization`, the signal is sent, and someone with `can_connect` uses **Reconnect**, the same sign-in
flow, which updates the same connection.

### Permissions

`IntegrationPermissionPolicy` gains `can_view_connections`, `can_connect` and `can_disconnect`, defaulting to
`integrations.view_connection`, `integrations.add_connection` and `integrations.delete_connection`. Hosts and
consuming packages may also call the services behind their own permission checks (blackmesa-social will, with its
account permission).

### HTTP API and HTML UI

- `GET v1/integrations/<slug>/connections/`: connections without tokens (account, name, scopes, status, expiry,
  connected by, dates).
- `POST v1/integrations/<slug>/connections/authorize/` (CSRF-protected): `{"authorization_url": ...}`; the SPA
  navigates there.
- `GET v1/integrations/<slug>/oauth/callback/`: the provider's redirect target. It finishes the sign-in and redirects
  to `return_to` only if `url_has_allowed_host_and_scheme` accepts it (`INTEGRATIONS_OAUTH_ALLOWED_REDIRECT_HOSTS`),
  else to the integration's detail page. Errors are shown or passed as a query code, never with token data.
- `POST v1/integrations/<slug>/connections/<id>/reconnect/` (CSRF-protected): `{"authorization_url": ...}` for
  signing the same account in again.
- `DELETE v1/integrations/<slug>/connections/<id>/`.
- OpenAPI updated; Problem Details for errors. The HTML UI gets a "Connect" button, the connection list with each
  status, "Reconnect" (highlighted when reauthorization is needed) and "Disconnect" on the integration's page. The admin lists connections read-only (no token values) with a disconnect
  action.

### Settings

| Setting | Default | Meaning |
|---|---|---|
| `INTEGRATIONS_OAUTH_REDIRECT_BASE` | from the request | Absolute base for the callback URL, for hosts behind proxies or with a separate API domain. The callback URL must be registered with the provider. |
| `INTEGRATIONS_OAUTH_ALLOWED_REDIRECT_HOSTS` | the request's host | Hosts `return_to` may point to (the host's SPA). |
| `INTEGRATIONS_OAUTH_TIMEOUT` | `10` | Seconds per token, refresh, revoke or account request. |
| `INTEGRATIONS_OAUTH_REFRESH_MARGIN` | `300` | Refresh when the access token expires within this many seconds. |

## Security requirements

- State is random, single use, bound to user and site, expires in 10 minutes, and is stored hashed. PKCE (S256) is
  on by default.
- Tokens are encrypted at rest, never returned, logged, put in `repr`, errors, forms, admin or test output.
  `rotate_encryption_keys` re-encrypts connections and pending requests too.
- No open redirect: `return_to` is checked against allowed hosts.
- Provider responses are untrusted: timeouts, size limits, and error messages that don't echo response bodies.
- The token exchange never runs inside a database transaction.
- Disconnecting deletes the tokens, whether or not the provider's revocation succeeded.

## Phases

### Phase A: Release 2.0.0 (prerequisite)

- Widen Django to `>=5.2,<7.0`; CI adds Python 3.14 and Django 6.1 (3.13 and 3.14 against 6.0 and 6.1, alongside
  the existing 5.2 entries).
- Fix anything 6.1 breaks; full checks.
- Tag `v2.0.0` and publish (owner).
- Deliverable: blackmesa-social can depend on `django-integrations>=2.0,<3.0` on Django 6.0 and 6.1.
- Progress (2026-11-18):
  - `Django>=5.2,<7.0` and the `Framework :: Django :: 6.1` classifier; CI adds 3.13 / 6.1 and 3.14 / 6.1 (3.14
    against 6.0 was already there).
  - Nothing broke on 6.1: 217 passed on Python 3.14 / Django 6.1.3 and on Python 3.13 / Django 6.1.3, with
    `PYTHONWARNINGS=always` and no warnings (scratch environments; the run included the owner's untracked
    `tests/test_migrate_legacy_credentials_example.py`). black, isort, flake8, mypy, bandit and
    `makemigrations --check` clean on 3.14 / 6.1.
  - Waiting on: a PR from `release/v2.0.0` into `develop`, CI, then `develop` into `main`; the owner tags `v2.0.0`
    and runs the publish workflow (it runs only on `main`).

### Phase B: Rule change and definitions

- `AGENTS.md` rule 9 amended (decision 2); `000-v2.md`'s deferred list points here.
- `OAUTH` capability, the `OAuth` dataclass, `ProviderAccount`, `fetch_account`, and the system checks.
- Deliverable: an OAuth integration can be defined and checked; nothing persisted yet.

### Phase C: Persistence

- `Connection` and `AuthorizationRequest` with an additive migration; key rotation covers them.
- Deliverable: tokens stored encrypted; migration tested; no change to `Credential`.

### Phase D: Services

- `begin_authorization`, `complete_authorization`, `get_access_token` (with compare-and-swap refresh), `disconnect`,
  listing; a fake provider for tests (no network).
- Deliverable: a full sign-in, refresh, reauthorisation and disconnect against the fake provider.

### Phase E: Interfaces

- Permission policy methods; the API endpoints and OpenAPI; HTML views and templates; admin.
- Deliverable: an SPA or the HTML UI can connect, list and disconnect accounts.

### Phase F: Documentation and a real provider

- `docs/oauth.md` (defining, the redirect URL to register, permissions, refresh, revocation, provider notes) and
  `docs/examples/google_youtube.py`; `docs/index.md`, README and CHANGELOG.
- Manual check with a real Google OAuth client in `develop/` (owner's credentials): connect, refresh, disconnect.
- Deliverable: release `v2.1.0` (owner tags and publishes).

## Test matrix (in addition to 000-v2.md's)

- Definition checks: missing `oauth`, missing `fetch_account`, missing client fields.
- State: tampered, replayed, expired, another user's, another site's; PKCE verifier sent.
- Callback: provider error, denied consent, token endpoint failure, `fetch_account` failure; nothing saved on failure.
- Reconnecting the same account updates one row and returns it to `active`; reconnecting as a different account is
  refused and leaves the connection unchanged; two accounts make two rows; scope isolation between sites.
- `connection_status_changed` sent once per real change, after saving.
- An integration with only an API key configured passes validation and refuses sign-in clearly; with neither, it
  fails validation.
- Refresh: within the margin, not before; concurrent refresh spends the refresh token once; `invalid_grant` →
  `needs_reauthorization`.
- Disconnect with and without a revoke URL, and when revocation fails.
- Non-disclosure: no token in API, HTML, admin, `repr`, logs or Problem Details.
- `return_to` open-redirect attempts.
- Permissions for every endpoint and view.
- Key rotation covers connection tokens.

## Checks

```bash
black --check .
isort --check-only .
flake8 .
mypy .
bandit -r src/
pytest --cov=integrations
```

## Branch

`new/oauth` from `develop` after Phase A's release; one PR into `develop`, then `main` for the release, as with v2.

## Out of scope

- OAuth 1.0a, client-credentials and device flows.
- Provider SDKs or bundled provider definitions in core (examples only).
- Using connections for user *login* (that's django-allauth's job).
- Webhooks.

## Progress log

- 2026-11-18 — Drafted from blackmesa-social's need; owner decisions 1–2 recorded.
- 2026-11-18 — Owner questions: an API key as an alternative (client fields may be optional; key and sign-in can
  coexist on one integration) and how tokens are updated (automatic refresh; Reconnect, same-account check and
  `connection_status_changed` added).
- 2026-11-18 — Approved. `plan.md` moved to `plans/000-v2.md` (owner); Phase A started on `release/v2.0.0`.
