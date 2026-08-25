from typing import Any

FIELD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "Field shape is defined per-integration (see the `fields` array "
        "on GET /integrations/{slug}/) - this schema describes the "
        "generic envelope common to every field entry."
    ),
    "properties": {
        "name": {"type": "string"},
        "type": {
            "type": "string",
            "enum": ["text", "secret", "url", "choice", "boolean", "integer"],
        },
        "label": {"type": "string"},
        "required": {"type": "boolean"},
        "help_text": {"type": "string"},
        "configured": {
            "type": "boolean",
            "description": "Secret fields only: whether a value is currently stored.",
        },
        "value": {
            "description": (
                "Non-secret fields only, and only on the configuration "
                "endpoint: the field's current stored value. Never present "
                "for secret fields."
            )
        },
    },
    "required": ["name", "type", "label", "required", "help_text"],
}

CONFIGURATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "integration": {"type": "string"},
        "configured": {"type": "boolean"},
        "fields": {"type": "array", "items": FIELD_SCHEMA},
    },
    "required": ["integration", "configured", "fields"],
}

PROBLEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": "RFC 9457 Problem Details.",
    "properties": {
        "type": {"type": "string"},
        "title": {"type": "string"},
        "status": {"type": "integer"},
        "detail": {"type": "string"},
        "errors": {
            "type": "object",
            "description": (
                "Present for validation failures (422): field name -> list "
                "of error messages, plus an optional __all__ bucket for "
                "cross-field errors."
            ),
            "additionalProperties": {"type": "array", "items": {"type": "string"}},
        },
    },
    "required": ["type", "title", "status"],
}

CONFIGURATION_REQUEST_BODY = {
    "description": (
        "A partial or full set of field values. A field omitted entirely "
        "preserves its currently stored value. An explicit JSON `null` "
        "clears a secret field (RFC 7396 JSON Merge Patch semantics) - "
        "sending `null` for a non-secret field is a validation error. PUT "
        "and PATCH behave identically: true full-replacement PUT semantics "
        "are impossible here, since secret fields are write-only and a "
        "client can never resend a value it was never given."
    ),
    "required": True,
    "content": {"application/json": {"schema": {"type": "object"}}},
}

PROBLEM_RESPONSES = {
    "401": {
        "description": "Not authenticated.",
        "content": {"application/problem+json": {"schema": PROBLEM_SCHEMA}},
    },
    "403": {
        "description": "Not permitted.",
        "content": {"application/problem+json": {"schema": PROBLEM_SCHEMA}},
    },
    "404": {
        "description": "No integration is registered for this slug.",
        "content": {"application/problem+json": {"schema": PROBLEM_SCHEMA}},
    },
    "422": {
        "description": "Validation failed.",
        "content": {"application/problem+json": {"schema": PROBLEM_SCHEMA}},
    },
}


def get_openapi_schema() -> dict[str, Any]:
    """
    A hand-written OpenAPI 3.0.3 document, not generated from the views -
    this package uses plain Django views (no DRF), so there's no
    schema-generation machinery to hook into. Describes the four fixed
    endpoints generically; per-integration field content is inherently
    dynamic and documented as such rather than faked as static.
    """
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "django-integrations API",
            "version": "1",
        },
        "paths": {
            "/integrations/": {
                "get": {
                    "summary": "List integrations visible to the caller.",
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "results": {
                                                "type": "array",
                                                "items": {"type": "object"},
                                            }
                                        },
                                    }
                                }
                            },
                        },
                        "401": PROBLEM_RESPONSES["401"],
                    },
                }
            },
            "/integrations/{slug}/": {
                "get": {
                    "summary": "Get one integration's definition.",
                    "parameters": [
                        {
                            "name": "slug",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {"schema": {"type": "object"}}
                            },
                        },
                        "401": PROBLEM_RESPONSES["401"],
                        "403": PROBLEM_RESPONSES["403"],
                        "404": PROBLEM_RESPONSES["404"],
                    },
                }
            },
            "/integrations/{slug}/configuration/": {
                "get": {
                    "summary": "Get the current stored configuration.",
                    "parameters": [
                        {
                            "name": "slug",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {"schema": CONFIGURATION_SCHEMA}
                            },
                        },
                        "401": PROBLEM_RESPONSES["401"],
                        "403": PROBLEM_RESPONSES["403"],
                        "404": PROBLEM_RESPONSES["404"],
                    },
                },
                "put": {
                    "summary": "Create or update the configuration.",
                    "requestBody": CONFIGURATION_REQUEST_BODY,
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {"schema": CONFIGURATION_SCHEMA}
                            },
                        },
                        "401": PROBLEM_RESPONSES["401"],
                        "403": PROBLEM_RESPONSES["403"],
                        "404": PROBLEM_RESPONSES["404"],
                        "422": PROBLEM_RESPONSES["422"],
                    },
                },
                "patch": {
                    "summary": "Create or update the configuration (identical to PUT).",
                    "requestBody": CONFIGURATION_REQUEST_BODY,
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {"schema": CONFIGURATION_SCHEMA}
                            },
                        },
                        "401": PROBLEM_RESPONSES["401"],
                        "403": PROBLEM_RESPONSES["403"],
                        "404": PROBLEM_RESPONSES["404"],
                        "422": PROBLEM_RESPONSES["422"],
                    },
                },
                "delete": {
                    "summary": "Remove the configuration, if any.",
                    "responses": {
                        "204": {"description": "No Content"},
                        "401": PROBLEM_RESPONSES["401"],
                        "403": PROBLEM_RESPONSES["403"],
                        "404": PROBLEM_RESPONSES["404"],
                    },
                },
            },
        },
    }
