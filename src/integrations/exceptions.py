class IntegrationError(Exception):
    """Base class for all django-integrations domain errors."""


class FieldValidationError(IntegrationError):
    """A single field failed validation."""

    def __init__(self, field_name: str, message: str):
        self.field_name = field_name
        self.message = message
        super().__init__(f"{field_name}: {message}")


class IntegrationValidationError(IntegrationError):
    """
    One or more fields failed validation, or cross-field validation failed.

    `errors` maps field name -> list of messages. Non-field-specific errors
    (raised by Integration.validate()) are collected under "__all__".
    """

    def __init__(self, errors: dict[str, list[str]]):
        self.errors = errors
        super().__init__(str(errors))


class DuplicateIntegrationError(IntegrationError):
    """A different class is already registered for this slug."""

    def __init__(self, slug: str):
        self.slug = slug
        super().__init__(f"An integration is already registered for slug {slug!r}.")


class IntegrationNotRegisteredError(IntegrationError):
    """No integration is registered for this slug."""

    def __init__(self, slug: str):
        self.slug = slug
        super().__init__(f"No integration is registered for slug {slug!r}.")


class DecryptionError(IntegrationError):
    """None of the configured ENCRYPTED_FIELD_KEYS could decrypt a value."""


class CapabilityNotSupportedError(IntegrationError):
    """test_connection() was invoked for an integration that doesn't
    declare the capability."""

    def __init__(self, slug: str):
        self.slug = slug
        super().__init__(f"{slug!r} does not support connection testing.")
