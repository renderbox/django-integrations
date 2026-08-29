from typing import Any, ClassVar

from integrations.capabilities import ConnectionTestResult
from integrations.exceptions import FieldValidationError, IntegrationValidationError
from integrations.fields.base import CLEAR, UNSET, IntegrationField


class IntegrationConfig:
    """
    Resolved, validated config + secrets for one integration.

    Independent of persistence: this is the output of Integration.clean(),
    not a database row. `secrets` only holds values actually supplied in
    this call - it is not a record of what is currently stored (that only
    exists once the service layer, Phase 6, applies this against a
    Credential).
    """

    def __init__(
        self,
        integration: "type[Integration]",
        config: dict[str, Any],
        secrets: dict[str, Any],
        cleared_secrets: frozenset[str] = frozenset(),
    ):
        self.integration = integration
        self.config = config
        self.secrets = secrets
        self.cleared_secrets = cleared_secrets

    def is_secret_configured(self, name: str) -> bool:
        return name in self.secrets

    def to_api_metadata(self) -> list[dict]:
        return [
            field.api_metadata(
                configured=(
                    self.is_secret_configured(field.name) if field.is_secret else None
                )
            )
            for field in self.integration.get_fields()
        ]


class Integration:
    """
    Declarative description of a third-party provider integration.

    Subclasses set `slug`, `name`, and `fields`. Nothing here touches
    persistence, the registry, or HTTP - see IntegrationConfig for the
    validated result and the `integrations.registry` module (Phase 3) for
    registration/discovery.
    """

    slug: ClassVar[str]
    name: ClassVar[str]
    description: ClassVar[str] = ""
    fields: ClassVar[list[IntegrationField]] = []
    capabilities: ClassVar[tuple[str, ...]] = ()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        seen: set[str] = set()
        for field in cls.fields:
            if field.name in seen:
                raise IntegrationValidationError(
                    {
                        "__all__": [
                            f"Duplicate field name {field.name!r} in {cls.__name__}."
                        ]
                    }
                )
            seen.add(field.name)

    @classmethod
    def get_fields(cls) -> list[IntegrationField]:
        return list(cls.fields)

    @classmethod
    def get_field(cls, name: str) -> IntegrationField:
        for field in cls.fields:
            if field.name == name:
                return field
        raise KeyError(name)

    @classmethod
    def config_fields(cls) -> list[IntegrationField]:
        return [field for field in cls.fields if not field.is_secret]

    @classmethod
    def secret_fields(cls) -> list[IntegrationField]:
        return [field for field in cls.fields if field.is_secret]

    @classmethod
    def clean(cls, data: dict[str, Any]) -> IntegrationConfig:
        """
        Validate raw input against this integration's field definitions.

        Runs field-level validation for every field, then (only if that
        passed) cross-field validation via `cls.validate()`. Raises a single
        aggregated IntegrationValidationError on any failure.
        """
        errors: dict[str, list[str]] = {}
        config: dict[str, Any] = {}
        secrets: dict[str, Any] = {}
        cleared_secrets: set[str] = set()

        for field in cls.fields:
            raw_value = data.get(field.name, UNSET)

            if raw_value is CLEAR:
                if not field.is_secret:
                    errors.setdefault(field.name, []).append(
                        "Only secret fields can be explicitly cleared."
                    )
                else:
                    cleared_secrets.add(field.name)
                continue

            try:
                cleaned = field.clean(raw_value)
            except FieldValidationError as exc:
                errors.setdefault(field.name, []).append(exc.message)
                continue

            if field.is_secret:
                if cleaned is not None:
                    secrets[field.name] = cleaned
            else:
                config[field.name] = cleaned

        if not errors:
            try:
                cls.validate(config, secrets)
            except IntegrationValidationError as exc:
                errors.update(exc.errors)

        if errors:
            raise IntegrationValidationError(errors)

        return IntegrationConfig(
            integration=cls,
            config=config,
            secrets=secrets,
            cleared_secrets=frozenset(cleared_secrets),
        )

    @classmethod
    def validate(cls, config: dict[str, Any], secrets: dict[str, Any]) -> None:
        """
        Cross-field/integration-level validation hook. No-op by default.

        Only called once every field has already passed its own validation.
        Override and raise IntegrationValidationError (with an "__all__"
        entry, or per-field entries) to fail. Do not perform external
        connection tests here - see Phase 11's test_connection().
        """

    @classmethod
    def test_connection(cls, config: IntegrationConfig) -> ConnectionTestResult:
        """
        Attempt to verify connectivity/credentials against the real
        provider. Only meaningful for integrations that declare
        "test_connection" in `capabilities` - override this on the
        subclass to implement the real check; the base implementation
        raises, so a declared-but-unimplemented capability fails loudly
        rather than pretending to work.

        `config.secrets` holds real, decrypted values here - this method
        needs them to actually authenticate. Never called as a side
        effect of clean()/save - only when a caller explicitly invokes it
        (via the services layer, which is the only place that should call
        this directly).

        Must not embed secret values in any exception it raises: unknown
        exceptions raised here are logged in full server-side by the
        service layer for operator debugging, but are not otherwise
        sanitized before being logged - "avoid leaking credentials in
        errors" is primarily a requirement on this method's
        implementation, not something the caller can guarantee for you.
        """
        raise NotImplementedError(
            f"{cls.__name__} does not implement test_connection()."
        )
