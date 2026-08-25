# django-integrations v2 Plan

## Objective

Rewrite `django-integrations` as a clean v2 while preserving the useful
core concept and providing a practical migration path for existing
installations.

The primary architectural change is to make declarative `Integration`
definitions the canonical source for provider identity, configuration
fields, secrets, validation, and capabilities.

The same definitions will drive:

-   Python integration behavior
-   credential persistence
-   server-side validation
-   the standards-following HTTP API
-   SPA metadata
-   generated Django forms
-   built-in HTML management views
-   supplementary Django admin behavior

## Success Criteria

v2 is successful when an application can define an integration once:

``` python
@register
class ExampleIntegration(Integration):
    slug = "example"
    name = "Example"

    fields = [
        TextField("account_id", label="Account ID", required=True),
        SecretField("api_key", label="API Key", required=True),
    ]
```

and receive, without duplicating provider schema:

-   validated configuration storage
-   encrypted secret storage
-   tenant-scoped retrieval
-   a built-in edit form
-   API field metadata for an SPA
-   secure partial updates
-   optional connection testing

No supported interface should expose a stored secret.

------------------------------------------------------------------------

## Phase 0 --- Baseline and Decisions

### Goals

Establish the current behavior and lock down the remaining architectural
choices before modifying persistence.

### Work

-   Inventory current public imports, URLs, views, forms, templates,
    models, encrypted fields, migrations, and settings.
-   Run and document the current test suite.
-   Establish supported Python versions.
-   Establish supported Django versions.
-   Confirmed whether the v2 Python API can be fully breaking or needs
    compatibility aliases.
-   Define the API URL/versioning convention.
-   Decide the API implementation approach:
    -   Django-native JSON views, or
    -   a focused API framework/dependency.
-   Confirmed the default tenant scope behavior using Django Sites.
-   Define how applications override scope resolution.
-   Confirmed the default permission policy and override mechanism.
-   Document the intended upgrade path from v1.

### Deliverable

An architecture decision section in project documentation with
unresolved decisions eliminated before model migration work begins.

------------------------------------------------------------------------

## Phase 1 --- Tooling and Test Foundation

### Goals

Create a reliable safety net before architectural changes.

### Work

-   Remove Poetry-specific configuration.
-   Keep and configure:
    -   Black
    -   isort
    -   flake8
-   Add:
    -   mypy
    -   Django typing support as appropriate
    -   Bandit
    -   pytest
    -   pytest-django
    -   coverage
-   Create dedicated test settings and test URL configuration.
-   Remove test dependence on the development project.
-   Remove use of private Django internals from tests.
-   Establish CI checks.

### Target checks

``` bash
black --check .
isort --check-only .
flake8 .
mypy .
bandit -r src/
pytest --cov=integrations
```

### Deliverable

Current supported v1 behavior covered by a clean test harness.

------------------------------------------------------------------------

## Phase 2 --- Core Integration Schema

### Goals

Implement the new domain abstraction without initially changing
credential persistence.

### Work

Create:

-   `Integration`
-   `IntegrationField`
-   `TextField`
-   `SecretField`
-   `URLField`
-   `ChoiceField`
-   `BooleanField`
-   `IntegerField`
-   `IntegrationConfig`
-   integration exceptions

Field definitions should support:

-   name
-   label
-   required
-   help text
-   default where appropriate
-   type-specific validation
-   API metadata
-   Django form-field generation or a clean adapter to it

### Important behavior

`SecretField("api_key")` represents a provider concept. It must not know
that a legacy model happens to contain `private_key`.

### Validation

Implement two levels:

1.  field validation
2.  integration-level/cross-field validation

Do not include external connection tests in configuration validation.

### Deliverable

Provider schemas can be expressed without writing models, forms, or API
serializers.

------------------------------------------------------------------------

## Phase 3 --- Integration Registry

### Goals

Provide deterministic discovery and retrieval of integration
definitions.

### Work

Implement:

-   `register`
-   `unregister`
-   `get`
-   `all`
-   duplicate-slug protection

Support:

-   application-defined integrations
-   Django app registration
-   future third-party provider packages

Add Django system checks for:

-   duplicate slugs
-   missing/invalid slugs
-   missing names
-   duplicate field names
-   invalid field definitions
-   reserved names where applicable

### Deliverable

Applications can register and resolve integrations through a stable
public API.

------------------------------------------------------------------------

## Phase 4 --- Persistence v2

### Goals

Move from provider-shaped database columns to schema-driven
configuration storage.

### Target model

Conceptually:

``` python
class Credential(models.Model):
    integration = models.CharField(max_length=100)
    site = models.ForeignKey(...)
    config = models.JSONField(default=dict)
    secrets = EncryptedJSONField(default=dict)
    created_at = ...
    updated_at = ...
```

Final naming may change during implementation.

### Work

-   Add stable integration identifier/slug to persisted credentials.
-   Add non-secret JSON configuration storage.
-   Add encrypted JSON secret storage.
-   Improve reverse relation naming.
-   Review `null=True`/`blank=True` usage.
-   Review URL-specific fields during migration.
-   Define uniqueness constraints based on the Phase 0 multiple-instance
    decision.
-   Preserve legacy fields while migration is in progress.
-   Create additive migrations.

### Migration strategy

Potential mappings:

``` text
client_id    -> config["client_id"]
client_url   -> config["client_url"]
public_key   -> secrets["public_key"]
private_key  -> secrets["private_key"]
```

`attrs` requires special handling because v1 does not identify which
values are sensitive.

Do not automatically classify unknown `attrs` values unless it is
demonstrably safe.

### Deliverable

New integrations can use `config` and encrypted `secrets` without
relying on legacy provider columns.

------------------------------------------------------------------------

## Phase 5 --- Encryption Hardening

### Goals

Make secret storage operationally safe.

### Work

-   Implement/refine `EncryptedJSONField`.
-   Preserve multi-key decryption.
-   Encrypt new writes with the primary key.
-   Raise an explicit exception when no configured key can decrypt
    ciphertext.
-   Never return ciphertext as a fallback plaintext value.
-   Centralize encryption settings.
-   Add Django checks for missing or malformed encryption configuration.
-   Add a key-rotation management command.
-   Ensure decrypted secrets are not exposed through logs or
    representations.

### Rotation workflow

Support:

1.  add new primary key
2.  retain old key(s) for decryption
3.  run rotation command
4.  verify successful rewrite
5.  remove retired key

### Deliverable

Documented and tested encryption and key-rotation lifecycle.

------------------------------------------------------------------------

## Phase 6 --- Credential and Integration Services

### Goals

Create the shared application layer used by every interface.

### Responsibilities

Services should handle:

-   integration lookup
-   scope resolution
-   credential lookup
-   configuration loading
-   configuration validation
-   secret-safe create/update
-   partial update semantics
-   explicit secret clearing
-   configured-state calculation
-   deletion
-   connection testing
-   permission enforcement at the appropriate boundary

### Critical update semantics

For secrets:

``` text
field omitted
    -> preserve stored secret

new value supplied
    -> replace stored secret

explicit clear operation
    -> remove stored secret
```

Never interpret an omitted secret as a request to erase it.

### Deliverable

API, HTML views, and admin no longer need direct provider-specific
persistence logic.

------------------------------------------------------------------------

## Phase 7 --- Tenant Scope and Authorization

### Goals

Make multi-tenant safety explicit and testable.

### Work

-   Introduce `IntegrationScope` or equivalent.
-   Implement default Django Sites resolver.
-   Provide a documented custom resolver hook.
-   Prevent cross-scope reads and writes.
-   Introduce permission/policy abstraction.
-   Provide sensible Django-permission defaults.
-   Cover view/configure/delete/test operations.
-   Test malicious or accidental cross-tenant access.

### Deliverable

Tenant isolation and authorization are enforced independently of UI
choice.

------------------------------------------------------------------------

## Phase 8 --- Standards-Following HTTP API

### Goals

Provide a stable public HTTP interface suitable for React and other SPA
clients.

### Candidate resources

Exact routes should be finalized before implementation, but the API
should support concepts equivalent to:

``` text
GET    /api/v2/integrations/
GET    /api/v2/integrations/{slug}/
GET    /api/v2/integrations/{slug}/configuration/
PUT    /api/v2/integrations/{slug}/configuration/
PATCH  /api/v2/integrations/{slug}/configuration/
DELETE /api/v2/integrations/{slug}/configuration/
POST   /api/v2/integrations/{slug}/test/
```

### Standards

-   JSON media types
-   correct HTTP status codes
-   clear PUT/PATCH behavior
-   RFC 9457 Problem Details
-   authentication integration
-   CSRF-safe session authentication
-   tenant/scope authorization
-   OpenAPI schema
-   explicit versioning
-   no permissive CORS defaults

### Secret representation

Stored secrets must never be returned.

Example metadata:

``` json
{
  "name": "api_key",
  "type": "secret",
  "label": "API Key",
  "required": true,
  "configured": true
}
```

### Error handling

Create a consistent mapping from domain exceptions to HTTP Problem
Details.

### Deliverable

An SPA can discover, display, configure, update, remove, and test
integrations without provider-specific server endpoints.

------------------------------------------------------------------------

## Phase 9 --- Built-in Django Forms and Views

### Goals

Provide a complete server-rendered alternative to the SPA.

### Work

Generate forms from integration definitions.

Provide views/routes for:

-   integration list
-   integration detail
-   configure/edit
-   delete/reset where appropriate
-   test connection where supported

Requirements:

-   use the shared service layer
-   respect scope resolution
-   respect permission policies
-   never prepopulate secret inputs with stored values
-   indicate whether secrets are already configured
-   preserve existing secrets when secret fields are left untouched
-   use CSRF protection
-   make templates overrideable by host projects

### Deliverable

Applications can manage tenant integrations without implementing a
custom frontend.

------------------------------------------------------------------------

## Phase 10 --- Django Admin

### Goals

Retain a useful operator interface without making it part of the primary
user workflow.

### Work

-   Update list display and filters.
-   Make integration type/slug visible.
-   Ensure secret fields cannot be casually revealed.
-   Consider configured/status indicators.
-   Reuse services where mutations require v2 behavior.
-   Avoid duplicating provider validation.

### Deliverable

Safe supplementary administration for staff users.

------------------------------------------------------------------------

## Phase 11 --- Connection Testing and Capabilities

### Goals

Support provider-specific behavior without bloating the base interface.

### Work

Define a small capability mechanism.

Initial useful capability:

``` text
test_connection
```

Potential future capabilities:

``` text
webhooks
oauth
```

Do not build speculative capability implementations until required.

`test_connection()` must remain separate from configuration validation.

Define a typed result such as `ConnectionTestResult`.

External calls must:

-   use timeouts
-   handle provider/network failures cleanly
-   avoid leaking credentials in errors
-   map appropriately to API and HTML responses

### Deliverable

Interfaces can discover whether an integration supports connection
testing and expose the action consistently.

------------------------------------------------------------------------

## Phase 12 --- Documentation and Example Integrations

### Goals

Make the intended v2 architecture obvious to package consumers.

### Documentation

Cover:

-   installation
-   settings
-   encryption keys
-   defining an integration
-   registering integrations
-   fields
-   config vs secrets
-   tenant scopes
-   permissions
-   API
-   built-in HTML UI
-   connection testing
-   key rotation
-   migration from v1
-   writing third-party provider packages

### Examples

Implement a small set of representative test/example integrations
demonstrating:

-   simple API key
-   configuration + secret
-   cross-field validation
-   test connection

Avoid adding heavyweight provider SDK dependencies merely for
documentation.

### Deliverable

A developer can implement a new integration without reading package
internals.

------------------------------------------------------------------------

## Phase 13 --- v1 Cleanup and Deprecation Removal

### Goals

Remove legacy structure only after migration and compatibility
requirements are satisfied.

### Candidates

-   legacy credential columns
-   legacy forms
-   obsolete view patterns
-   old API scaffolding
-   stale/dead code
-   obsolete settings
-   obsolete compatibility aliases
-   development-only assumptions

### Rule

Do not delete a legacy persistence mechanism merely because the v2
equivalent exists. First ensure:

1.  data migration exists
2.  migration behavior is tested
3.  upgrade documentation exists
4.  supported compatibility window has been decided

### Deliverable

A coherent v2 codebase rather than v1 plus a parallel v2 architecture.

------------------------------------------------------------------------

## Cross-Cutting Test Matrix

Every relevant phase should expand tests rather than deferring testing
to the end.

### Core

-   field definitions
-   field validation
-   integration validation
-   registry behavior
-   duplicate handling
-   configuration representation

### Persistence

-   config persistence
-   encrypted secret persistence
-   plaintext absent from database
-   legacy migration
-   partial updates
-   explicit clears

### Security

-   secrets absent from API responses
-   secrets absent from HTML
-   secrets absent from error responses
-   cross-tenant access rejected
-   unauthorized mutations rejected
-   decryption failure explicit
-   key rotation successful

### API

-   list
-   detail
-   PUT
-   PATCH
-   DELETE
-   test
-   invalid JSON
-   validation errors
-   authentication failures
-   authorization failures
-   RFC 9457 response structure

### HTML

-   list
-   detail
-   generated form
-   validation
-   secret preservation
-   test connection
-   permission enforcement
-   scope enforcement

------------------------------------------------------------------------

## Deferred / Explicitly Out of Scope for Initial v2

Unless required by a concrete integration, do not make these initial-v2
blockers:

-   generic OAuth flow framework
-   webhook processing framework
-   Celery integration
-   React components
-   provider SDK bundles
-   deep provider inheritance hierarchies
-   generic repository/DTO architecture
-   automatic CORS management

The architecture should leave room for these without implementing them
speculatively.

------------------------------------------------------------------------

## Recommended Implementation Order

The phases above are intentionally dependency ordered:

``` text
Baseline
   ↓
Tooling/tests
   ↓
Integration schema
   ↓
Registry
   ↓
Persistence
   ↓
Encryption
   ↓
Services
   ↓
Scope/permissions
   ↓
Native Django API
   ↓
Optional DRF adapter
   ↓
HTML UI
   ↓
Admin
   ↓
Capabilities
   ↓
Documentation
   ↓
Legacy cleanup
```

Do not begin with a large rewrite of `models.py`, API views, or
templates.

The first meaningful v2 implementation milestone should prove this
vertical concept:

``` text
Integration definition
        ↓
field schema
        ↓
validation
        ↓
registry
```

The next should prove:

``` text
Integration definition
        ↓
service
        ↓
config + encrypted secrets
```

Only after those are stable should API and HTML interfaces be rebuilt on
top.

------------------------------------------------------------------------
