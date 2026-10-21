"""Single-asset endpoints and the signed file server (local storage)."""

from __future__ import annotations

import uuid

from flask import Blueprint, current_app, jsonify, request, send_file
from sqlalchemy import func, select

from app.api.common import doc, page, pagination, parse_body
from app.errors import APIError, NotFound
from app.extensions import db
from app.models import Asset, AssetKind
from app.schemas.requests import AssetUpdateIn
from app.schemas.serializers import asset_out
from app.security.auth import current_user, login_required
from app.services import asset_service, project_service
from app.storage.backends import LocalStorage, StorageError, get_storage, read_signed_file_token

bp = Blueprint("assets", __name__, url_prefix="/api/assets")
files_bp = Blueprint("files", __name__, url_prefix="/api/files")


@bp.get("")
@doc("List all my assets", tags=["Assets"], query={"kind": "image|video|audio|text"})
@login_required
def list_assets():
    user = current_user()
    limit, offset = pagination(default_limit=50)
    query = select(Asset).where(Asset.owner_id == user.id)
    kind = request.args.get("kind")
    if kind:
        try:
            query = query.where(Asset.kind == AssetKind(kind))
        except ValueError as exc:
            raise APIError("Unknown asset kind.", code="invalid_filter") from exc
    total = db.session.scalar(select(func.count()).select_from(query.subquery()))
    assets = db.session.scalars(query.order_by(Asset.created_at.desc()).limit(limit).offset(offset)).all()
    return jsonify(page([asset_out(a) for a in assets], total, limit, offset))


@bp.post("")
@doc("Upload a file not tied to a project (multipart field 'file')", tags=["Assets"], multipart=True)
@login_required
def upload_asset():
    file = request.files.get("file")
    if file is None:
        raise APIError("Attach the file in a multipart field named 'file'.", code="file_required",
                       status_code=422)
    asset = asset_service.save_upload(current_user(), None, file.stream, file.filename)
    return jsonify({"asset": asset_out(asset)}), 201


@bp.get("/<uuid:asset_id>")
@doc("Get asset details", tags=["Assets"])
@login_required
def get_asset(asset_id: uuid.UUID):
    return jsonify({"asset": asset_out(asset_service.get_owned_asset(current_user(), asset_id))})


@bp.patch("/<uuid:asset_id>")
@doc("Rename an asset or move it into one of my projects", tags=["Assets"], body=AssetUpdateIn)
@login_required
def update_asset(asset_id: uuid.UUID):
    user = current_user()
    asset = asset_service.get_owned_asset(user, asset_id)
    data = parse_body(AssetUpdateIn).model_dump(exclude_unset=True)
    if data.get("display_name"):
        asset.display_name = data["display_name"]
    if "project_id" in data:
        if data["project_id"] is not None:
            project_service.get_owned_project(user, data["project_id"])
        asset.project_id = data["project_id"]
    db.session.commit()
    return jsonify({"asset": asset_out(asset)})


@bp.delete("/<uuid:asset_id>")
@doc("Delete an asset permanently", tags=["Assets"])
@login_required
def delete_asset(asset_id: uuid.UUID):
    asset_service.delete_asset(asset_service.get_owned_asset(current_user(), asset_id))
    return "", 204


@bp.get("/<uuid:asset_id>/url")
@doc("Get a short-lived link to view or download the file", tags=["Assets"])
@login_required
def asset_url(asset_id: uuid.UUID):
    asset = asset_service.get_owned_asset(current_user(), asset_id)
    if not get_storage().exists(asset.storage_key):
        raise NotFound("The file for this asset is missing from storage.", code="file_missing")
    return jsonify({"url": asset_service.download_url(asset),
                    "expires_in": current_app.config["SIGNED_URL_TTL_SECONDS"]})


@files_bp.get("/<token>")
@doc("Serve a file from a signed link (local storage only)", tags=["Assets"], auth="none")
def serve_signed_file(token: str):
    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        raise NotFound("Not found.")
    try:
        data = read_signed_file_token(token)
        path = storage.path_for(data["k"])
    except (StorageError, KeyError) as exc:
        raise APIError("This link is invalid or has expired.", code="invalid_link", status_code=403) from exc
    if not path.is_file():
        raise NotFound("The file is missing.", code="file_missing")
    # send_file streams from disk and supports Range requests for video seeking.
    response = send_file(path, mimetype=data["t"], download_name=data["f"], as_attachment=False,
                         conditional=True, max_age=0)
    response.headers["Cache-Control"] = "private, max-age=300"
    response.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response
