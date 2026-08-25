from typing import Any

from django.http import JsonResponse

PROBLEM_CONTENT_TYPE = "application/problem+json"


def problem_response(
    *,
    status: int,
    title: str,
    detail: str | None = None,
    type_: str = "about:blank",
    **extra: Any,
) -> JsonResponse:
    """
    One RFC 9457 (Problem Details for HTTP APIs) response shape, used for
    every error this API returns.
    """
    body: dict[str, Any] = {"type": type_, "title": title, "status": status}
    if detail:
        body["detail"] = detail
    body.update(extra)
    return JsonResponse(body, status=status, content_type=PROBLEM_CONTENT_TYPE)
