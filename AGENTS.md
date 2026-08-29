# AGENTS.md

## Purpose

This repository contains `django-integrations`, a reusable Django
package for defining, storing, validating, and managing third-party
integrations.

Version 2 is a deliberate modernization of the package. The goal is not
to preserve historical implementation patterns. Preserve useful behavior
and upgrade compatibility where practical, but prefer a clean,
consistent architecture over incremental refactoring of v1 cruft.

The central v2 concept is:

> An integration definition is the canonical description of an
> integration. Persistence, the HTTP API, built-in Django views/forms,
> and administrative interfaces consume that definition rather than
> independently implementing provider-specific behavior.

## v2 Goals

-   Provide a clean, typed Python API for defining integrations.
-   Support declarative integration configuration schemas.
-   Separate non-secret configuration from encrypted secrets.
-   Provide secure credential storage with key rotation.
-   Support multi-tenant/site-scoped integrations.
-   Provide a standards-following HTTP API suitable for SPAs.
-   Provide built-in Django views, forms, URLs, and templates for
    user-managed integrations.
-   Keep Django admin support, but do not treat admin as the primary
    management interface.
-   Ensure API and HTML interfaces use the same validation and service
    layer.
-   Make provider-specific integrations extensible without growing the
    core package indefinitely.
-   Preserve a practical upgrade path from v1.
-   Keep the package small and understandable.

## Architectural Principles

### 1. Integration definitions are the source of truth

Provider requirements must not be independently duplicated across
models, forms, API schemas, and views.

An integration definition should describe:

-   slug
-   name
-   description
-   configuration fields
-   secret fields
-   validation
-   capabilities
-   optional provider-specific behavior

Example target API:

``` python
from integrations import Integration, register
from integrations.fields import SecretField, TextField


@register
class ZoomIntegration(Integration):
    slug = "zoom"
    name = "Zoom"
    description = "Zoom video conferencing integration"

    fields = [
        TextField("api_key", label="API Key", required=True),
        SecretField("api_secret", label="API Secret", required=True),
    ]
```

### 2. Do not make `Credential` the provider schema

The database model stores integration configuration. It should not
dictate the fields every provider is allowed to use.

The target persistence model is conceptually:

``` python
class Credential(models.Model):
    integration = models.CharField(max_length=100)
    site = models.ForeignKey(...)
    config = models.JSONField(default=dict)
    secrets = EncryptedJSONField(default=dict)
    created_at = ...
    updated_at = ...
```

Existing v1 fields may remain temporarily for migration compatibility.

### 3. Separate configuration from secrets

Non-sensitive values belong in `config`.

Sensitive values belong in encrypted `secrets`.

Do not store tokens, passwords, API secrets, private keys, refresh
tokens, or equivalent sensitive values in an unencrypted JSON field.

Secrets must never be returned to clients after storage.

API and form representations may indicate that a secret is configured,
but must not reveal the stored value.

### 4. Keep HTTP and template layers thin

The API and built-in Django views/forms must call shared services.

Do not put provider behavior, persistence rules, secret handling, tenant
resolution, or cross-field validation directly in views.

Preferred dependency direction:

``` text
SPA -> HTTP API -----------\
                            -> services -> registry/integrations -> persistence
HTML views/forms ----------/
Django admin -------------/
```

### 5. Multi-tenancy is a core requirement

Integrations are user-editable and may be configured independently for
multiple tenant sites.

Django Sites may remain the default scope mechanism, but avoid
scattering `request.site` assumptions throughout the package.

Tenant/scope resolution should have an explicit abstraction so
applications can evolve beyond Django Sites without rewriting
integration logic.

Never permit a request to read or mutate credentials outside its
resolved scope.

### 6. Authorization is separate from tenancy

Resolving a tenant does not prove that a user may manage its
integrations.

Provide an explicit permission/policy layer for operations such as:

-   view
-   configure
-   delete
-   test connection

The default may use Django permissions, but applications must be able to
override policy behavior.

### 7. Validation and connection testing are different operations

Configuration validation should be deterministic and normally local.

Examples:

-   required values
-   URL validity
-   choice validity
-   field relationships

Connection testing may contact an external provider and must be treated
separately.

Do not make external network calls as an implicit side effect of saving
configuration unless explicitly required and documented.

### 8. Avoid unnecessary inheritance

Do not create deep hierarchies such as
`OAuthIntegration -> RESTIntegration -> ...`.

Prefer a small `Integration` base class plus declarative fields and
capabilities.

Provider-specific methods such as `get_client()` may exist on a provider
implementation without becoming mandatory methods on every integration.

### 9. Integration instances are unique per site

The v2 domain model assumes one configured instance of a given integration per site.

Conceptually:

```text
(site, integration) -> one Credential
```

Use an explicit database uniqueness constraint and enforce the same rule through services.

Do not add generic support for multiple named instances, provider accounts, or credential sets per site unless the project owner explicitly changes this requirement.

### 10. Provider dependencies should remain outside core where practical

The core package should not accumulate every provider SDK.

The architecture should permit packages such as:

``` text
django-integrations-stripe
django-integrations-slack
django-integrations-zoom
```

without requiring them initially.

## Integration Fields

Start with a deliberately small field system:

-   `TextField`
-   `SecretField`
-   `URLField`
-   `ChoiceField`
-   `BooleanField`
-   `IntegerField`

Do not prematurely add OAuth-specific field abstractions.

Field definitions should be immutable where practical and capable of
driving:

-   server-side validation
-   Django form generation
-   API/SPA metadata

A field definition describes the provider domain, not the database
layout.

Prefer:

``` python
SecretField("secret_key")
```

Do not require:

``` python
SecretField("private_key", model_field="private_key")
```

## Integration Configuration

Use an `IntegrationConfig` or equivalent abstraction rather than passing
arbitrary dictionaries throughout the package.

It must correctly distinguish:

-   stored non-secret values
-   stored secret values
-   a configured but hidden secret
-   a missing update value, meaning preserve the current secret
-   an explicit clear operation, meaning remove the secret

Updating an unrelated field must never erase an existing secret.

## Registry

Provide a registry for integration definitions.

Expected operations include:

``` python
registry.register(...)
registry.unregister(...)
registry.get(...)
registry.all(...)
```

Duplicate slugs must fail clearly.

Registration should support application-defined integrations and future
third-party integration packages.

Avoid excessive import/discovery magic.

## API Requirements

The API is a supported public interface intended for SPA consumption.

It does not have to use Django REST Framework. Choose implementation
dependencies deliberately and keep the HTTP contract independent of a
particular API framework.

The API should follow established web standards, including:

-   JSON request and response bodies
-   appropriate HTTP methods
-   consistent status codes
-   PATCH semantics for partial updates
-   RFC 9457 Problem Details for errors
-   documented authentication expectations
-   CSRF-safe behavior for session authentication
-   tenant/scope authorization
-   OpenAPI documentation/schema
-   explicit API versioning policy

CORS configuration belongs to the host application unless the package
has a compelling reason to manage it.

Stored secrets are write-only over HTTP.

A response may contain:

``` json
{
  "name": "secret_key",
  "type": "secret",
  "required": true,
  "configured": true
}
```

It must never contain the stored secret value.

## Built-in HTML Management UI

The package must provide a functional server-rendered management
experience for applications that do not want to implement an SPA
management screen.

Expected concepts include:

-   integration list
-   integration detail
-   integration edit/configure
-   connection test where supported

Forms should be generated from integration field definitions rather than
requiring a provider-specific `ModelForm`.

Saving a generated form must go through the same service layer used by
the API.

Templates should be easy for host applications to override using normal
Django template resolution.

Do not expose stored secret values back into form fields.

## Django Admin

Retain useful Django admin support for operators and developers.

Admin is supplementary. Do not design user-facing multi-tenant workflows
around Django admin.

Admin must follow the same secret-handling requirements as every other
interface.

## Encryption

Encryption is a security boundary.

Requirements:

-   encrypt secret values at rest
-   support multiple decryption keys
-   encrypt new values with the primary/current key
-   provide a supported key-rotation workflow
-   fail explicitly when ciphertext cannot be decrypted
-   never silently return ciphertext as though it were a usable secret
-   avoid logging decrypted values
-   avoid exposing secrets through `repr`, API serialization, forms, or
    error messages

Provide a management command for re-encrypting stored secrets with the
current primary key.

## Django System Checks

Use Django's checks framework for configuration errors that can be
detected before runtime.

Potential checks include:

-   missing encryption configuration
-   duplicate integration slugs
-   invalid integration definitions
-   duplicate field names
-   invalid/reserved field names
-   malformed settings

## Package Structure

Target roughly:

``` text
src/integrations/
├── __init__.py
├── apps.py
├── admin.py
├── checks.py
├── conf.py
├── exceptions.py
├── permissions.py
├── scopes.py
├── api/
│   ├── __init__.py
│   ├── urls.py
│   ├── views.py
│   ├── schemas.py
│   ├── serializers.py
│   ├── errors.py
│   └── openapi.py
├── contrib/
│   └── drf/
│       ├── __init__.py
│       ├── urls.py
│       ├── views.py
│       ├── serializers.py
│       └── permissions.py
├── fields/
│   ├── __init__.py
│   ├── base.py
│   └── encrypted.py
├── forms/
│   ├── __init__.py
│   └── integrations.py
├── integrations/
│   ├── __init__.py
│   ├── base.py
│   └── registry.py
├── models/
│   ├── __init__.py
│   └── credential.py
├── services/
│   ├── __init__.py
│   ├── credentials.py
│   ├── integrations.py
│   └── validation.py
├── views/
│   ├── __init__.py
│   └── integrations.py
├── templates/
│   └── integrations/
└── management/
    └── commands/
```

This is a direction, not a requirement to create empty modules before
they are useful.

Do not over-architect the package with repository classes, DTO
hierarchies, or service abstractions that do not solve a concrete
problem.

## Compatibility and Migration

v2 may substantially improve the Python API.

Database compatibility should receive more care because existing
applications may contain persisted credentials.

Prefer additive schema changes and data migrations before destructive
cleanup.

Potential migration path:

``` text
client_id    -> config["client_id"]
client_url   -> config["client_url"]
public_key   -> secrets["public_key"]
private_key  -> secrets["private_key"]
attrs        -> explicitly classified config/secrets
```

Do not blindly migrate arbitrary `attrs` values into secrets or
configuration if their sensitivity cannot be known.

Document manual migration requirements where automatic classification is
unsafe.

## Coding Standards

Target supported Python and Django versions declared by the package.

Use:

-   Black for formatting
-   isort for import ordering
-   flake8 for linting
-   mypy with appropriate Django typing support
-   Bandit for static security checks
-   pytest and pytest-django for tests
-   coverage for test coverage measurement

Remove Poetry-specific configuration.

Use standard package extras for optional integrations such as DRF. The base installation should depend only on Django and dependencies required by the core package.

Do not replace Black, isort, or flake8 with Ruff unless the project
owner explicitly decides to do so.

Prefer type annotations for public APIs and important internal
boundaries.

## Testing

Tests must not depend on the development/demo project to initialize
Django.

Provide dedicated test settings and URLs.

Test behavior at the correct layer.

At minimum cover:

-   model persistence
-   encryption/decryption
-   encryption key rotation
-   decryption failure
-   registry registration and duplicate handling
-   field validation
-   integration-level validation
-   configuration updates
-   secret preservation during partial updates
-   explicit secret clearing
-   scope isolation
-   authorization
-   API responses
-   RFC 9457 errors
-   API secret non-disclosure
-   generated forms
-   HTML secret non-disclosure
-   connection-test behavior
-   Django system checks
-   migrations where practical

Avoid direct manipulation of private Django internals in tests.

## Security Rules

When touching credentials or APIs:

1.  Assume configuration values may be attacker-controlled.
2.  Never log secrets.
3.  Never return stored secrets.
4.  Enforce tenant isolation server-side.
5.  Enforce authorization server-side.
6.  Treat outbound provider calls as untrusted network operations.
7.  Use timeouts for outbound HTTP.
8.  Do not weaken CSRF protections to make SPA integration easier.
9.  Do not add permissive CORS defaults.
10. Run Bandit and relevant tests for security-sensitive changes.

## Development Workflow

Before implementing a v2 feature:

1.  Read this file and `plan.md`.
2.  Inspect the current implementation and migrations.
3.  Identify the public behavior affected.
4.  Prefer tests that describe the desired v2 behavior before large
    refactors.
5.  Implement the smallest coherent architectural slice.
6.  Run formatting, linting, typing, security, and tests.
7.  Update documentation when public behavior changes.
8.  Update `plan.md` as milestones are completed or architectural
    decisions change.

Expected quality checks should eventually be equivalent to:

``` bash
black --check .
isort --check-only .
flake8 .
mypy .
bandit -r src/
pytest --cov=integrations
```

## Agent Guardrails

Agents working on this repository must:

-   not rewrite migrations casually
-   not remove v1 persisted fields until the migration path is
    implemented and approved
-   not expose secrets for convenience in tests, APIs, templates, or
    admin
-   not introduce a new API framework without documenting the tradeoff
-   not introduce provider SDKs into core without a clear reason
-   not duplicate validation between API and HTML layers
-   not couple provider definitions to database column names
-   not add abstractions merely to satisfy a pattern
-   not silently make breaking public API changes outside the agreed v2
    scope
-   not reduce tenant isolation or authorization checks
-   not change the agreed formatting/linting toolchain without approval

When uncertain, favor explicit behavior, secure defaults, Django
conventions, and a small public API.
