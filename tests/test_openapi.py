import json

from integrations.api.openapi import get_openapi_schema


class TestGetOpenapiSchema:
    def test_returns_expected_shape(self):
        schema = get_openapi_schema()
        assert schema["openapi"] == "3.0.3"
        paths = schema["paths"]
        assert "/integrations/" in paths
        assert "/integrations/{slug}/" in paths
        assert "/integrations/{slug}/configuration/" in paths

    def test_configuration_path_has_all_four_methods(self):
        schema = get_openapi_schema()
        methods = schema["paths"]["/integrations/{slug}/configuration/"]
        assert set(methods) == {"get", "put", "patch", "delete"}


class TestOpenApiSchemaEndpoint:
    def test_served_as_json_without_authentication(self, client):
        response = client.get("/api/v1/openapi.json")
        assert response.status_code == 200
        body = json.loads(response.content)
        assert body["openapi"] == "3.0.3"
