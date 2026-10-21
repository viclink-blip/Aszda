"""Small helpers shared by the route modules, plus the OpenAPI metadata decorator."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import request
from pydantic import BaseModel

from app.errors import APIError


def parse_body[M: BaseModel](model: type[M]) -> M:
    if not request.is_json:
        raise APIError("Send a JSON body with Content-Type: application/json.",
                       code="unsupported_media_type", status_code=415)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise APIError("The request body must be a JSON object.", code="invalid_json", status_code=400)
    return model.model_validate(data)


def pagination(default_limit: int = 20, max_limit: int = 100) -> tuple[int, int]:
    try:
        limit = int(request.args.get("limit", default_limit))
        offset = int(request.args.get("offset", 0))
    except ValueError as exc:
        raise APIError("limit and offset must be numbers.", code="invalid_pagination") from exc
    return max(1, min(limit, max_limit)), max(0, offset)


def page(items: list[Any], total: int, limit: int, offset: int) -> dict[str, Any]:
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def idempotency_key() -> str:
    key = request.headers.get("Idempotency-Key", "").strip()
    if not 8 <= len(key) <= 128 or not all(c.isalnum() or c in "-_:." for c in key):
        raise APIError("Send an Idempotency-Key header (8-128 letters, digits, '-', '_', ':' or '.'). "
                       "Reuse the same key when retrying the same request.",
                       code="idempotency_key_required", status_code=400)
    return key


def doc(summary: str, *, tags: list[str], body: type[BaseModel] | None = None, auth: str = "user",
        query: dict[str, str] | None = None, multipart: bool = False) -> Callable:
    """Attach OpenAPI metadata to a view. auth is one of: none, user, admin, refresh_cookie."""

    def decorator(view: Callable) -> Callable:
        view._openapi = {"summary": summary, "tags": tags, "body": body, "auth": auth,
                         "query": query or {}, "multipart": multipart}
        return view

    return decorator
