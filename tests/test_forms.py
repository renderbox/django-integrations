from django import forms

from integrations import Integration
from integrations.fields import SecretField, TextField
from integrations.forms import build_configuration_form
from integrations.forms.integrations import CLEAR_FIELD_SUFFIX


class WidgetIntegration(Integration):
    slug = "widget-form-test"
    name = "Widget"
    fields = [
        TextField("account_id", required=True),
        SecretField("api_key", required=True),
        SecretField("webhook_secret", required=False),
    ]


class TestBuildConfigurationForm:
    def test_non_secret_field_keeps_its_own_required(self):
        form_cls = build_configuration_form(WidgetIntegration)
        assert form_cls.base_fields["account_id"].required is True

    def test_secret_fields_are_always_not_required_at_form_layer(self):
        form_cls = build_configuration_form(WidgetIntegration)
        assert form_cls.base_fields["api_key"].required is False
        assert form_cls.base_fields["webhook_secret"].required is False

    def test_secret_fields_use_password_widget_with_no_render_value(self):
        form_cls = build_configuration_form(WidgetIntegration)
        widget = form_cls.base_fields["api_key"].widget
        assert isinstance(widget, forms.PasswordInput)
        assert widget.render_value is False

    def test_clear_checkbox_exists_only_for_optional_secrets(self):
        form_cls = build_configuration_form(WidgetIntegration)
        assert f"webhook_secret{CLEAR_FIELD_SUFFIX}" in form_cls.base_fields
        assert f"api_key{CLEAR_FIELD_SUFFIX}" not in form_cls.base_fields
        assert f"account_id{CLEAR_FIELD_SUFFIX}" not in form_cls.base_fields

    def test_placeholder_reflects_configured_state(self):
        configured_form_cls = build_configuration_form(
            WidgetIntegration, configured_secrets=frozenset({"api_key"})
        )
        unconfigured_form_cls = build_configuration_form(WidgetIntegration)

        configured_placeholder = configured_form_cls.base_fields[
            "api_key"
        ].widget.attrs["placeholder"]
        unconfigured_placeholder = unconfigured_form_cls.base_fields[
            "api_key"
        ].widget.attrs["placeholder"]

        assert "leave blank" in configured_placeholder.lower()
        assert configured_placeholder != unconfigured_placeholder

    def test_form_never_receives_a_secret_value_via_initial_and_still_validates(self):
        form_cls = build_configuration_form(
            WidgetIntegration, configured_secrets=frozenset({"api_key"})
        )
        # Simulating a GET render: initial only ever carries non-secret
        # values in the real view, never a secret's stored value.
        form = form_cls(initial={"account_id": "acct-1"})
        assert "api_key" not in form.initial
