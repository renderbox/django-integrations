from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views import View

from integrations import conf, registry
from integrations.base import CLEAR, Integration, IntegrationConfig
from integrations.capabilities import TEST_CONNECTION
from integrations.exceptions import (
    CapabilityNotSupportedError,
    IntegrationNotRegisteredError,
    IntegrationValidationError,
)
from integrations.forms import build_configuration_form
from integrations.forms.integrations import CLEAR_FIELD_SUFFIX
from integrations.services import credentials as services


def _field_rows(config: IntegrationConfig) -> list[dict[str, Any]]:
    """
    A small, template-friendly view of the current configuration: a
    value for non-secret fields, only a configured flag for secrets.
    Local to this module rather than IntegrationConfig.to_api_metadata()
    (Phase 2), which is deliberately values-free for the field-schema use
    case, or api/serializers.py's serialize_configuration() (Phase 8),
    which would mean the HTML layer depending on the API layer.
    """
    rows = []
    for field in config.integration.get_fields():
        row: dict[str, Any] = {
            "name": field.name,
            "label": field.label,
            "is_secret": field.is_secret,
        }
        if field.is_secret:
            row["configured"] = config.is_secret_configured(field.name)
        else:
            row["value"] = config.config.get(field.name)
        rows.append(row)
    return rows


class BaseHTMLView(LoginRequiredMixin, View):
    """
    scope is resolved lazily (on first access from get()/post(), not in
    setup()) so an unauthenticated request never triggers the DB query
    scope resolution needs - LoginRequiredMixin's redirect happens in
    dispatch(), which runs after setup() but before get()/post().
    """

    @property
    def scope(self) -> Any:
        if not hasattr(self, "_scope"):
            self._scope = conf.resolve_scope(self.request)
        return self._scope

    def _get_integration(self, slug: str) -> type[Integration]:
        try:
            return registry.get(slug)
        except IntegrationNotRegisteredError:
            raise Http404(f"No integration is registered for slug {slug!r}.")

    def _require_permission(self, method_name: str, slug: str) -> None:
        policy = conf.get_permission_policy()
        check = getattr(policy, method_name)
        if not check(self.request.user, self.scope, slug):
            raise PermissionDenied


class IntegrationListView(BaseHTMLView):
    template_name = "integrations/list.html"

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        policy = conf.get_permission_policy()
        integrations = [
            {
                "integration": integration_cls,
                "configured": services.is_configured(self.scope, integration_cls.slug),
            }
            for integration_cls in registry.all()
            if policy.can_view(request.user, self.scope, integration_cls.slug)
        ]
        return render(request, self.template_name, {"integrations": integrations})


class IntegrationDetailView(BaseHTMLView):
    template_name = "integrations/detail.html"

    def get(
        self, request: HttpRequest, slug: str, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        integration_cls = self._get_integration(slug)
        self._require_permission("can_view", slug)
        config = services.get_config(self.scope, slug)
        is_configured = services.is_configured(self.scope, slug)
        policy = conf.get_permission_policy()
        context = {
            "integration": integration_cls,
            "fields": _field_rows(config),
            "is_configured": is_configured,
            "can_configure": policy.can_configure(request.user, self.scope, slug),
            "can_delete": policy.can_delete(request.user, self.scope, slug),
            "can_test_connection": (
                TEST_CONNECTION in integration_cls.capabilities
                and is_configured
                and policy.can_test_connection(request.user, self.scope, slug)
            ),
        }
        return render(request, self.template_name, context)


class ConfigureView(BaseHTMLView):
    """
    GET pre-fills non-secret values from the stored configuration; secret
    fields never receive an initial value at all, regardless of whether
    they're currently configured - see build_configuration_form() for why
    a blank secret submission preserves rather than clears.
    """

    template_name = "integrations/configure_form.html"

    def _configured_secrets(self, integration_cls: type[Integration], slug: str):
        config = services.get_config(self.scope, slug)
        return (
            config,
            frozenset(
                field.name
                for field in integration_cls.secret_fields()
                if config.is_secret_configured(field.name)
            ),
        )

    def get(
        self, request: HttpRequest, slug: str, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        integration_cls = self._get_integration(slug)
        self._require_permission("can_configure", slug)
        config, configured_secrets = self._configured_secrets(integration_cls, slug)
        form_cls = build_configuration_form(
            integration_cls, configured_secrets=configured_secrets
        )
        form = form_cls(initial=dict(config.config))
        return render(
            request,
            self.template_name,
            {"integration": integration_cls, "form": form},
        )

    def post(
        self, request: HttpRequest, slug: str, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        integration_cls = self._get_integration(slug)
        self._require_permission("can_configure", slug)
        _, configured_secrets = self._configured_secrets(integration_cls, slug)
        form_cls = build_configuration_form(
            integration_cls, configured_secrets=configured_secrets
        )
        form = form_cls(data=request.POST)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {"integration": integration_cls, "form": form},
            )

        payload: dict[str, Any] = {}
        for field in integration_cls.get_fields():
            if field.is_secret:
                clear_key = f"{field.name}{CLEAR_FIELD_SUFFIX}"
                if not field.required and form.cleaned_data.get(clear_key):
                    payload[field.name] = CLEAR
                    continue
                value = form.cleaned_data.get(field.name)
                if not value:
                    continue  # blank -> omitted -> preserved by save_config()
                payload[field.name] = value
            else:
                payload[field.name] = form.cleaned_data.get(field.name)

        try:
            services.save_config(self.scope, slug, payload)
        except IntegrationValidationError as exc:
            for field_name, field_messages in exc.errors.items():
                target = None if field_name == "__all__" else field_name
                for message in field_messages:
                    form.add_error(target, message)
            return render(
                request,
                self.template_name,
                {"integration": integration_cls, "form": form},
            )

        return redirect("integration-detail", slug=slug)


class DeleteView(BaseHTMLView):
    template_name = "integrations/confirm_delete.html"

    def get(
        self, request: HttpRequest, slug: str, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        integration_cls = self._get_integration(slug)
        self._require_permission("can_delete", slug)
        return render(request, self.template_name, {"integration": integration_cls})

    def post(
        self, request: HttpRequest, slug: str, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        self._get_integration(slug)
        self._require_permission("can_delete", slug)
        services.delete_config(self.scope, slug)
        return redirect("integration-list")


class TestConnectionView(BaseHTMLView):
    def post(
        self, request: HttpRequest, slug: str, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        self._get_integration(slug)
        self._require_permission("can_test_connection", slug)
        try:
            result = services.test_connection(self.scope, slug)
        except CapabilityNotSupportedError:
            raise Http404(f"{slug!r} does not support connection testing.")

        if result.success:
            messages.success(request, result.message or "Connection test succeeded.")
        else:
            messages.error(request, result.message or "Connection test failed.")
        return redirect("integration-detail", slug=slug)
