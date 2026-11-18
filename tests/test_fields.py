from django import forms

from integrations.exceptions import FieldValidationError
from integrations.fields import (
    BooleanField,
    ChoiceField,
    IntegerField,
    SecretField,
    TextField,
    URLField,
)


class TestTextField:
    def test_clean_valid_value(self):
        field = TextField("name")
        assert field.clean("hello") == "hello"

    def test_required_missing_raises(self):
        field = TextField("name")
        try:
            field.clean("")
        except FieldValidationError as exc:
            assert exc.field_name == "name"
        else:
            raise AssertionError("expected FieldValidationError")

    def test_optional_missing_returns_none_by_default(self):
        field = TextField("name", required=False)
        assert field.clean("") is None

    def test_optional_missing_returns_default(self):
        field = TextField("name", required=False, default="fallback")
        assert field.clean(None) == "fallback"

    def test_to_form_field(self):
        field = TextField("name", label="Name", help_text="help")
        form_field = field.to_form_field()
        assert isinstance(form_field, forms.CharField)
        assert form_field.label == "Name"
        assert form_field.help_text == "help"


class TestSecretField:
    def test_is_secret(self):
        assert SecretField("api_key").is_secret is True
        assert TextField("name").is_secret is False

    def test_api_metadata_never_contains_a_value(self):
        field = SecretField("api_key")
        metadata = field.api_metadata(configured=True)
        assert "value" not in metadata
        assert metadata["configured"] is True
        assert metadata["type"] == "secret"

    def test_form_field_uses_password_widget_without_render_value(self):
        field = SecretField("api_key")
        form_field = field.to_form_field()
        assert isinstance(form_field.widget, forms.PasswordInput)
        assert form_field.widget.render_value is False


class TestURLField:
    def test_valid_url(self):
        field = URLField("client_url")
        assert field.clean("https://example.com") == "https://example.com"

    def test_invalid_url_raises(self):
        field = URLField("client_url")
        try:
            field.clean("not a url")
        except FieldValidationError:
            pass
        else:
            raise AssertionError("expected FieldValidationError")

    def test_to_form_field(self):
        assert isinstance(URLField("client_url").to_form_field(), forms.URLField)


class TestChoiceField:
    def test_valid_choice(self):
        field = ChoiceField("mode", choices=["a", "b"])
        assert field.clean("a") == "a"

    def test_invalid_choice_raises(self):
        field = ChoiceField("mode", choices=["a", "b"])
        try:
            field.clean("c")
        except FieldValidationError:
            pass
        else:
            raise AssertionError("expected FieldValidationError")

    def test_pair_choices_preserved(self):
        field = ChoiceField("mode", choices=[("a", "Alpha"), ("b", "Beta")])
        assert field.clean("a") == "a"
        metadata = field.api_metadata()
        assert metadata["choices"] == [
            {"value": "a", "label": "Alpha"},
            {"value": "b", "label": "Beta"},
        ]

    def test_to_form_field(self):
        assert isinstance(
            ChoiceField("mode", choices=["a", "b"]).to_form_field(), forms.ChoiceField
        )


class TestBooleanField:
    def test_defaults_to_not_required(self):
        assert BooleanField("enabled").required is False

    def test_truthy_string_coercion(self):
        field = BooleanField("enabled")
        assert field.clean("true") is True
        assert field.clean("no") is False

    def test_bool_passthrough(self):
        field = BooleanField("enabled")
        assert field.clean(True) is True
        assert field.clean(False) is False

    def test_to_form_field(self):
        form_field = BooleanField("enabled").to_form_field()
        assert isinstance(form_field, forms.BooleanField)
        assert form_field.required is False


class TestIntegerField:
    def test_valid_integer(self):
        field = IntegerField("port")
        assert field.clean("42") == 42

    def test_non_numeric_raises(self):
        field = IntegerField("port")
        try:
            field.clean("abc")
        except FieldValidationError:
            pass
        else:
            raise AssertionError("expected FieldValidationError")

    def test_below_min_raises(self):
        field = IntegerField("port", min_value=1)
        try:
            field.clean(0)
        except FieldValidationError:
            pass
        else:
            raise AssertionError("expected FieldValidationError")

    def test_above_max_raises(self):
        field = IntegerField("port", max_value=100)
        try:
            field.clean(101)
        except FieldValidationError:
            pass
        else:
            raise AssertionError("expected FieldValidationError")

    def test_to_form_field(self):
        assert isinstance(IntegerField("port").to_form_field(), forms.IntegerField)
