"""Asset uploads, generated outputs, downloads and deletion."""

from __future__ import annotations

import hashlib
import io
import logging
import tempfile
import uuid
from typing import BinaryIO

from flask import current_app
from sqlalchemy import select

from app.errors import APIError, NotFound
from app.extensions import db
from app.models import Asset, AssetKind, AssetSource, User
from app.storage.backends import get_storage
from app.storage.sniff import EXTENSIONS, sniff

log = logging.getLogger(__name__)

CHUNK = 1024 * 1024


def get_owned_asset(user: User, asset_id: uuid.UUID) -> Asset:
    asset = db.session.get(Asset, asset_id)
    # 404 rather than 403, so other users' asset IDs cannot be confirmed to exist.
    if asset is None or asset.owner_id != user.id:
        raise NotFound("Asset not found.")
    return asset


def _new_key(owner_id: uuid.UUID, asset_id: uuid.UUID, extension: str) -> str:
    return f"users/{owner_id}/assets/{asset_id}.{extension}"


def save_upload(user: User, project_id: uuid.UUID | None, stream: BinaryIO, filename: str | None,
                display_name: str | None = None) -> Asset:
    """Stream an upload to a temp file (never fully into memory), check it, then store it."""
    max_bytes = current_app.config["MAX_UPLOAD_MB"] * 1024 * 1024
    digest = hashlib.sha256()
    size = 0
    with tempfile.SpooledTemporaryFile(max_size=8 * CHUNK) as tmp:
        head = b""
        while True:
            chunk = stream.read(CHUNK)
            if not chunk:
                break
            if len(head) < 64:
                head += chunk[: 64 - len(head)]
            size += len(chunk)
            if size > max_bytes:
                raise APIError(f"Files can be at most {current_app.config['MAX_UPLOAD_MB']} MB.",
                               code="file_too_large", status_code=413)
            digest.update(chunk)
            tmp.write(chunk)
        if size == 0:
            raise APIError("The file is empty.", code="empty_file", status_code=422)
        detected = sniff(head)
        if detected is None:
            raise APIError(
                "This file type is not supported. Upload PNG, JPEG, WebP, GIF, MP4, WebM, MOV, "
                "MP3, WAV, OGG or FLAC.", code="unsupported_file_type", status_code=415)
        tmp.seek(0)
        asset_id = uuid.uuid4()
        key = _new_key(user.id, asset_id, detected.extension)
        get_storage().save(key, tmp, detected.mime)

    clean_name = (filename or "").replace("\\", "/").split("/")[-1][:255] or None
    asset = Asset(
        id=asset_id, owner_id=user.id, project_id=project_id, kind=detected.kind,
        source=AssetSource.UPLOAD, storage_key=key, original_filename=clean_name,
        display_name=(display_name or clean_name or f"Upload.{detected.extension}")[:255],
        mime_type=detected.mime, size_bytes=size, sha256=digest.hexdigest(),
    )
    db.session.add(asset)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        get_storage().delete(key)
        raise
    return asset


def save_generated(*, owner_id: uuid.UUID, project_id: uuid.UUID | None, job_id: uuid.UUID,
                   data: bytes | BinaryIO, mime_type: str, kind: AssetKind, display_name: str,
                   duration_seconds: float | None = None, width: int | None = None,
                   height: int | None = None) -> Asset:
    """Store a provider's output. The caller commits."""
    extension = EXTENSIONS.get(mime_type, "bin")
    asset_id = uuid.uuid4()
    key = _new_key(owner_id, asset_id, extension)
    stream = io.BytesIO(data) if isinstance(data, bytes) else data
    digest = hashlib.sha256()
    with tempfile.SpooledTemporaryFile(max_size=8 * CHUNK) as tmp:
        size = 0
        while chunk := stream.read(CHUNK):
            digest.update(chunk)
            size += len(chunk)
            tmp.write(chunk)
        tmp.seek(0)
        get_storage().save(key, tmp, mime_type)
    asset = Asset(
        id=asset_id, owner_id=owner_id, project_id=project_id, generation_job_id=job_id, kind=kind,
        source=AssetSource.GENERATED, storage_key=key, display_name=display_name[:255],
        mime_type=mime_type, size_bytes=size, sha256=digest.hexdigest(),
        duration_seconds=duration_seconds, width=width, height=height,
    )
    db.session.add(asset)
    return asset


def download_url(asset: Asset) -> str:
    name = asset.display_name
    ext = EXTENSIONS.get(asset.mime_type)
    if ext and not name.lower().endswith("." + ext):
        name = f"{name}.{ext}"
    return get_storage().download_url(asset.storage_key, filename=name, content_type=asset.mime_type)


def delete_asset(asset: Asset) -> None:
    key = asset.storage_key
    db.session.delete(asset)
    db.session.commit()
    delete_storage_objects([key])


def storage_keys_for_owner(owner_id: uuid.UUID) -> list[str]:
    return list(db.session.scalars(select(Asset.storage_key).where(Asset.owner_id == owner_id)))


def storage_keys_for_project(project_id: uuid.UUID) -> list[str]:
    return list(db.session.scalars(select(Asset.storage_key).where(Asset.project_id == project_id)))


def delete_storage_objects(keys: list[str]) -> None:
    storage = get_storage()
    for key in keys:
        try:
            storage.delete(key)
        except Exception:  # noqa: BLE001 — a leftover file must not break the user's request
            log.exception("Could not delete stored object %s; run `flask aszda cleanup-storage`", key)
