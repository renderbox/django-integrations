from django import forms

from integrations.base import Integration

CLEAR_FIELD_SUFFIX = "__clear"


def build_configuration_form(
    integration_cls: type[Integration],
    *,
    configured_secrets: frozenset[str] = frozenset(),
) -> type[forms.Form]:
    """
    Dynamically builds a plain forms.Form (not a ModelForm - Credential
    isn't provider-shaped) from an integration's field definitions.

    Secret fields are always required=False at the form-validation layer,
    regardless of the domain field's own requiredness: leaving one blank
    on an edit means "don't change it" (services.save_config()'s
    preserve-on-omit merge, Phase 6), which the form must always allow
    submitting. The domain-level requiredness is enforced afterward, once
    the view merges the submission with whatever's already stored.

    Optional secret fields also get a same-named `{name}__clear`
    checkbox, since an HTML form has no equivalent of JSON `null` for
    explicitly clearing a value.
    """
    attrs: dict[str, forms.Field] = {}
    for field in integration_cls.get_fields():
        if field.is_secret:
            configured = field.name in configured_secrets
            placeholder = (
                "Currently set - leave blank to keep it"
                if configured
                else "Not currently set"
            )
            attrs[field.name] = field.to_form_field(
                required=False,
                widget=forms.PasswordInput(
                    render_value=False, attrs={"placeholder": placeholder}
                ),
            )
            if not field.required:
                attrs[f"{field.name}{CLEAR_FIELD_SUFFIX}"] = forms.BooleanField(
                    required=False, label=f"Clear {field.label}"
                )
        else:
            attrs[field.name] = field.to_form_field()
    return type("ConfigurationForm", (forms.Form,), attrs)
