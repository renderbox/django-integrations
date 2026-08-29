from typing import Any, ClassVar, Optional, Sequence, Union

from django import forms
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import URLValidator

from integrations.exceptions import FieldValidationError

# Sentinel meaning "this key was absent from the input" - distinct from an
# explicit None/blank value. Used by Integration.clean() when resolving
# partial updates; a bare field definition treats it the same as "missing".
UNSET = object()

# Sentinel meaning "explicitly remove this secret". Only meaningful for
# secret fields; full preserve/clear-against-stored-data semantics are
# implemented by the service layer (Phase 6), not here.
CLEAR = object()


class IntegrationField:
    """
    Describes one configuration value a provider integration accepts.

    A field definition describes the provider domain (name, type, whether
    it's a secret) - never a database column. Treated as write-once by
    convention: nothing here provides setters for the constructor
    arguments after construction.
    """

    field_type: ClassVar[str]
    is_secret: ClassVar[bool] = False

    def __init__(
        self,
        name: str,
        *,
        label: Optional[str] = None,
        required: bool = True,
        help_text: str = "",
        default: Any = None,
    ):
        self.name = name
        self.label = label or name.replace("_", " ").title()
        self.required = required
        self.help_text = help_text
        self.default = default

    def clean(self, value: Any) -> Any:
        """Validate and normalize a raw value. Raises FieldValidationError."""
        if value is UNSET or value is None or value == "":
            if self.required:
                raise FieldValidationError(self.name, "This field is required.")
            return self.default
        return self._clean(value)

    def _clean(self, value: Any) -> Any:
        """Type-specific coercion/validation. Override in subclasses."""
        return value

    def to_form_field(self, **overrides: Any) -> forms.Field:
        raise NotImplementedError

    def api_metadata(self, *, configured: Optional[bool] = None) -> dict:
        metadata = {
            "name": self.name,
            "type": self.field_type,
            "label": self.label,
            "required": self.required,
            "help_text": self.help_text,
        }
        if self.is_secret and configured is not None:
            metadata["configured"] = configured
        return metadata


class TextField(IntegrationField):
    field_type = "text"

    def _clean(self, value: Any) -> str:
        return str(value)

    def to_form_field(self, **overrides: Any) -> forms.Field:
        kwargs: dict = {
            "label": self.label,
            "required": self.required,
            "help_text": self.help_text,
        }
        kwargs.update(overrides)
        return forms.CharField(**kwargs)


class SecretField(TextField):
    field_type = "secret"
    is_secret = True

    def to_form_field(self, **overrides: Any) -> forms.Field:
        kwargs: dict = {
            "label": self.label,
            "required": self.required,
            "help_text": self.help_text,
            "widget": forms.PasswordInput(render_value=False),
        }
        kwargs.update(overrides)
        return forms.CharField(**kwargs)


class URLField(TextField):
    field_type = "url"

    def _clean(self, value: Any) -> str:
        value = str(value)
        try:
            URLValidator()(value)
        except DjangoValidationError:
            raise FieldValidationError(self.name, "Enter a valid URL.")
        return value

    def to_form_field(self, **overrides: Any) -> forms.Field:
        kwargs: dict = {
            "label": self.label,
            "required": self.required,
            "help_text": self.help_text,
        }
        kwargs.update(overrides)
        return forms.URLField(**kwargs)


class ChoiceField(IntegrationField):
    field_type = "choice"

    def __init__(
        self, name: str, *, choices: Sequence[Union[str, tuple]], **kwargs: Any
    ):
        super().__init__(name, **kwargs)
        self.choices = tuple(
            choice if isinstance(choice, tuple) else (choice, choice)
            for choice in choices
        )

    def _clean(self, value: Any) -> Any:
        valid_values = {value for value, _ in self.choices}
        if value not in valid_values:
            raise FieldValidationError(self.name, f"{value!r} is not a valid choice.")
        return value

    def api_metadata(self, *, configured: Optional[bool] = None) -> dict:
        metadata = super().api_metadata(configured=configured)
        metadata["choices"] = [
            {"value": value, "label": label} for value, label in self.choices
        ]
        return metadata

    def to_form_field(self, **overrides: Any) -> forms.Field:
        kwargs: dict = {
            "label": self.label,
            "required": self.required,
            "help_text": self.help_text,
            "choices": self.choices,
        }
        kwargs.update(overrides)
        return forms.ChoiceField(**kwargs)


class BooleanField(IntegrationField):
    field_type = "boolean"

    def __init__(self, name: str, *, required: bool = False, **kwargs: Any):
        super().__init__(name, required=required, **kwargs)

    def _clean(self, value: Any) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)

    def to_form_field(self, **overrides: Any) -> forms.Field:
        kwargs: dict = {
            "label": self.label,
            "required": False,
            "help_text": self.help_text,
        }
        kwargs.update(overrides)
        return forms.BooleanField(**kwargs)


class IntegerField(IntegrationField):
    field_type = "integer"

    def __init__(
        self,
        name: str,
        *,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
        **kwargs: Any,
    ):
        super().__init__(name, **kwargs)
        self.min_value = min_value
        self.max_value = max_value

    def _clean(self, value: Any) -> int:
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise FieldValidationError(self.name, "Enter a whole number.")
        if self.min_value is not None and value < self.min_value:
            raise FieldValidationError(
                self.name,
                f"Ensure this value is greater than or equal to {self.min_value}.",
            )
        if self.max_value is not None and value > self.max_value:
            raise FieldValidationError(
                self.name,
                f"Ensure this value is less than or equal to {self.max_value}.",
            )
        return value

    def to_form_field(self, **overrides: Any) -> forms.Field:
        kwargs: dict = {
            "label": self.label,
            "required": self.required,
            "help_text": self.help_text,
            "min_value": self.min_value,
            "max_value": self.max_value,
        }
        kwargs.update(overrides)
        return forms.IntegerField(**kwargs)
