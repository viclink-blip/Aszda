"""Builds an OpenAPI 3.1 document from the registered routes and their @doc metadata.

GET /api/openapi.json — import it into Swagger Editor, Postman or Insomnia.
"""

from __future__ import annotations

import re
from typing import Any

from flask import Blueprint, current_app, jsonify

from app.api.common import doc

bp = Blueprint("openapi", __name__, url_prefix="/api")

_CONVERTER = re.compile(r"<(?:(\w+):)?(\w+)>")


def build_spec() -> dict[str, Any]:
    paths: dict[str, dict] = {}
    schemas: dict[str, Any] = {}
    for rule in current_app.url_map.iter_rules():
        if not rule.rule.startswith("/api"):
            continue
        view = current_app.view_functions[rule.endpoint]
        meta = getattr(view, "_openapi", None)
        if meta is None:
            continue
        path = _CONVERTER.sub(lambda m: "{" + m.group(2) + "}", rule.rule)
        params = []
        for converter, name in _CONVERTER.findall(rule.rule):
            schema = {"type": "string", "format": "uuid"} if converter == "uuid" else {"type": "string"}
            params.append({"name": name, "in": "path", "required": True, "schema": schema})
        for name, description in meta["query"].items():
            params.append({"name": name, "in": "query", "required": False,
                           "description": description, "schema": {"type": "string"}})
        for method in sorted(rule.methods - {"HEAD", "OPTIONS"}):
            op: dict[str, Any] = {"summary": meta["summary"], "tags": meta["tags"],
                                  "operationId": rule.endpoint.replace(".", "_"),
                                  "parameters": params,
                                  "responses": {"default": {"description": "See docs/API.md"}}}
            if meta["auth"] in ("user", "admin"):
                op["security"] = [{"bearerAuth": []}]
            elif meta["auth"] == "refresh_cookie":
                op["security"] = [{"refreshCookie": []}]
            if meta["body"] is not None:
                model = meta["body"]
                schema = model.model_json_schema(ref_template="#/components/schemas/{model}")
                schemas.update(schema.pop("$defs", {}))
                schemas[model.__name__] = schema
                op["requestBody"] = {"required": True, "content": {"application/json": {
                    "schema": {"$ref": f"#/components/schemas/{model.__name__}"}}}}
            elif meta["multipart"]:
                op["requestBody"] = {"required": True, "content": {"multipart/form-data": {"schema": {
                    "type": "object", "properties": {"file": {"type": "string", "format": "binary"},
                                                     "display_name": {"type": "string"}},
                    "required": ["file"]}}}}
            paths.setdefault(path, {})[method.lower()] = op
    return {
        "openapi": "3.1.0",
        "info": {"title": "ASZDA Studio API", "version": "0.1.0",
                 "description": "Errors use the shape {\"error\": {\"code\", \"message\", \"details\"}}."},
        "paths": dict(sorted(paths.items())),
        "components": {
            "schemas": schemas,
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
                "refreshCookie": {"type": "apiKey", "in": "cookie", "name": "aszda_refresh"},
            },
        },
    }


@bp.get("/openapi.json")
@doc("This OpenAPI document", tags=["Health"], auth="none")
def openapi_json():
    return jsonify(build_spec())
