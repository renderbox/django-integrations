import json

from integrations.api.errors import problem_response


class TestProblemResponse:
    def test_basic_shape(self):
        response = problem_response(status=404, title="Not found")
        assert response.status_code == 404
        assert response["Content-Type"] == "application/problem+json"
        body = json.loads(response.content)
        assert body == {"type": "about:blank", "title": "Not found", "status": 404}

    def test_includes_detail_when_given(self):
        response = problem_response(status=400, title="Bad", detail="explanation")
        body = json.loads(response.content)
        assert body["detail"] == "explanation"

    def test_omits_detail_when_blank(self):
        response = problem_response(status=400, title="Bad", detail="")
        body = json.loads(response.content)
        assert "detail" not in body

    def test_extra_kwargs_become_extension_members(self):
        response = problem_response(
            status=422, title="Validation failed", errors={"api_key": ["required"]}
        )
        body = json.loads(response.content)
        assert body["errors"] == {"api_key": ["required"]}
