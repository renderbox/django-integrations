import json
from typing import Any

from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, HttpResponseBase, JsonResponse
from django.views import View

from integrations import conf, registry
from integrations.api import serializers
from integrations.api.errors import problem_response
from integrations.api.openapi import get_openapi_schema
from integrations.base import CLEAR
from integrations.exceptions import (
    CapabilityNotSupportedError,
    IntegrationNotRegisteredError,
    IntegrationValidationError,
)
from integrations.services import credentials as services


def _parse_body(request: HttpRequest) -> dict[str, Any]:
    """
    Parses the request body as a JSON object, translating an explicit
    `null` for any field into the domain layer's CLEAR sentinel (RFC 7396
    JSON Merge Patch semantics - CLEAR isn't itself JSON-representable).
    """
    if not request.body:
        return {}
    data = json.loads(request.body)
    if not isinstance(data, dict):
        raise ValueError("Request body must be a JSON object.")
    return {key: (CLEAR if value is None else value) for key, value in data.items()}


class BaseAPIView(View):
    def dispatch(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponseBase:
        if not request.user.is_authenticated:
            return problem_response(status=401, title="Authentication required")
        self.scope = conf.resolve_scope(request)
        try:
            return super().dispatch(request, *args, **kwargs)
        except IntegrationNotRegisteredError as exc:
            return problem_response(
                status=404, title="Integration not found", detail=str(exc)
            )
        except CapabilityNotSupportedError as exc:
            return problem_response(
                status=404, title="Capability not supported", detail=str(exc)
            )
        except IntegrationValidationError as exc:
            return problem_response(
                status=422, title="Validation failed", errors=exc.errors
            )
        except PermissionDenied:
            return problem_response(status=403, title="Permission denied")
        except (json.JSONDecodeError, ValueError) as exc:
            return problem_response(
                status=400, title="Malformed request body", detail=str(exc)
            )

    def http_method_not_allowed(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        return problem_response(
            status=405,
            title="Method not allowed",
            detail=f"{request.method} is not supported for this endpoint.",
        )

    def _require_permission(self, method_name: str, slug: str) -> None:
        policy = conf.get_permission_policy()
        check = getattr(policy, method_name)
        if not check(self.request.user, self.scope, slug):
            raise PermissionDenied


class IntegrationListView(BaseAPIView):
    def get(self, request: HttpRequest) -> HttpResponse:
        policy = conf.get_permission_policy()
        results = [
            serializers.serialize_integration_summary(integration_cls, self.scope)
            for integration_cls in registry.all()
            if policy.can_view(request.user, self.scope, integration_cls.slug)
        ]
        return JsonResponse({"results": results})


class IntegrationDetailView(BaseAPIView):
    def get(self, request: HttpRequest, slug: str) -> HttpResponse:
        integration_cls = registry.get(slug)
        self._require_permission("can_view", slug)
        return JsonResponse(
            serializers.serialize_integration_summary(integration_cls, self.scope)
        )


class ConfigurationView(BaseAPIView):
    """
    PUT and PATCH are intentionally identical: both go through
    services.save_config()'s preserve-on-omit merge. True RFC 9110 PUT
    semantics (resend the complete representation) aren't achievable here
    - secret fields are write-only, so a client can never reconstruct a
    complete representation to resend in the first place.
    """

    def get(self, request: HttpRequest, slug: str) -> HttpResponse:
        registry.get(slug)
        self._require_permission("can_view", slug)
        config = services.get_config(self.scope, slug)
        is_configured = services.is_configured(self.scope, slug)
        return JsonResponse(
            serializers.serialize_configuration(config, is_configured=is_configured)
        )

    def put(self, request: HttpRequest, slug: str) -> HttpResponse:
        return self._save(request, slug)

    def patch(self, request: HttpRequest, slug: str) -> HttpResponse:
        return self._save(request, slug)

    def _save(self, request: HttpRequest, slug: str) -> HttpResponse:
        registry.get(slug)
        self._require_permission("can_configure", slug)
        data = _parse_body(request)
        services.save_config(self.scope, slug, data)
        config = services.get_config(self.scope, slug)
        return JsonResponse(
            serializers.serialize_configuration(config, is_configured=True)
        )

    def delete(self, request: HttpRequest, slug: str) -> HttpResponse:
        registry.get(slug)
        self._require_permission("can_delete", slug)
        services.delete_config(self.scope, slug)
        return HttpResponse(status=204)


class TestConnectionView(BaseAPIView):
    def post(self, request: HttpRequest, slug: str) -> HttpResponse:
        registry.get(slug)
        self._require_permission("can_test_connection", slug)
        result = services.test_connection(self.scope, slug)
        return JsonResponse({"success": result.success, "message": result.message})


class OpenAPISchemaView(View):
    """No authentication required - an API schema document is public by
    convention, same as any other API documentation."""

    def get(self, request: HttpRequest) -> HttpResponse:
        return JsonResponse(get_openapi_schema())
