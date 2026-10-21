"""Consistent JSON error responses.

Every error the API returns has the shape:
    {"error": {"code": "machine_readable_code", "message": "Human readable text", "details": {...}}}
Unexpected exceptions are logged with a reference ID and the client only sees that ID,
never a stack trace or internal detail.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from flask import Flask, jsonify
from pydantic import ValidationError
from werkzeug.exceptions import HTTPException

log = logging.getLogger(__name__)


class APIError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None,
                 details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details = details or {}


class NotFound(APIError):
    status_code = 404
    code = "not_found"


class Unauthorized(APIError):
    status_code = 401
    code = "unauthorized"


class Forbidden(APIError):
    status_code = 403
    code = "forbidden"


class Conflict(APIError):
    status_code = 409
    code = "conflict"


class PaymentRequired(APIError):
    status_code = 402
    code = "insufficient_credits"


class ServiceUnavailable(APIError):
    status_code = 503
    code = "service_unavailable"


def error_body(code: str, message: str, details: dict | None = None) -> dict:
    body: dict[str, Any] = {"code": code, "message": message}
    if details:
        body["details"] = details
    return {"error": body}


def validation_details(exc: ValidationError) -> dict:
    fields = []
    for err in exc.errors():
        fields.append({
            "field": ".".join(str(p) for p in err["loc"]),
            "message": err["msg"],
        })
    return {"fields": fields}


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(APIError)
    def handle_api_error(exc: APIError):
        return jsonify(error_body(exc.code, exc.message, exc.details)), exc.status_code

    @app.errorhandler(ValidationError)
    def handle_validation_error(exc: ValidationError):
        return jsonify(error_body("validation_error", "Some fields are invalid.",
                                  validation_details(exc))), 422

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException):
        code = (exc.name or "error").lower().replace(" ", "_")
        if exc.code == 429:
            return jsonify(error_body("rate_limited", "Too many requests. Please slow down.")), 429
        if exc.code == 413:
            return jsonify(error_body("payload_too_large", "The upload is too large.")), 413
        return jsonify(error_body(code, exc.description or exc.name)), exc.code

    @app.errorhandler(Exception)
    def handle_unexpected(exc: Exception):
        reference = uuid.uuid4().hex[:12]
        log.exception("Unhandled error (ref=%s)", reference)
        return jsonify(error_body("internal_error",
                                  "Something went wrong on our side.",
                                  {"reference": reference})), 500
