"""Projects, characters, scenes (storyboard) and project assets."""

from __future__ import annotations

import uuid

from flask import Blueprint, jsonify, request
from sqlalchemy import func, select

from app.api.common import doc, page, pagination, parse_body
from app.errors import APIError
from app.extensions import db
from app.models import Asset, AssetKind, GenerationJob, ProjectStatus
from app.schemas.requests import (
    CharacterIn,
    CharacterUpdateIn,
    ProjectCreateIn,
    ProjectUpdateIn,
    SceneIn,
    SceneOrderIn,
    SceneUpdateIn,
)
from app.schemas.serializers import asset_out, character_out, job_out, project_out, scene_out
from app.security.auth import current_user, login_required
from app.services import asset_service, project_service

bp = Blueprint("projects", __name__, url_prefix="/api/projects")


@bp.get("")
@doc("List my projects", tags=["Projects"], query={"status": "draft|in_progress|completed|archived",
                                                    "q": "search in titles", "limit": "1-100",
                                                    "offset": "skip N"})
@login_required
def list_projects():
    limit, offset = pagination()
    status = request.args.get("status") or None
    try:
        status_enum = ProjectStatus(status) if status else None
    except ValueError as exc:
        raise APIError("Unknown status filter.", code="invalid_filter") from exc
    search = (request.args.get("q") or "").strip()[:100] or None
    projects, total = project_service.list_projects(current_user(), status=status_enum, search=search,
                                                    limit=limit, offset=offset)
    stats = project_service.project_stats([p.id for p in projects])
    return jsonify(page([project_out(p, stats.get(p.id)) for p in projects], total, limit, offset))


@bp.post("")
@doc("Create a project", tags=["Projects"], body=ProjectCreateIn)
@login_required
def create_project():
    data = parse_body(ProjectCreateIn).model_dump()
    project = project_service.create_project(current_user(), data)
    return jsonify({"project": project_out(project)}), 201


@bp.get("/<uuid:project_id>")
@doc("Get a project with its characters and scenes", tags=["Projects"])
@login_required
def get_project(project_id: uuid.UUID):
    project = project_service.get_owned_project(current_user(), project_id)
    stats = project_service.project_stats([project.id])
    return jsonify({
        "project": project_out(project, stats.get(project.id)),
        "characters": [character_out(c) for c in project.characters],
        "scenes": [scene_out(s) for s in project.scenes],
    })


@bp.patch("/<uuid:project_id>")
@doc("Update (rename, describe, change status)", tags=["Projects"], body=ProjectUpdateIn)
@login_required
def update_project(project_id: uuid.UUID):
    project = project_service.get_owned_project(current_user(), project_id)
    data = {k: v for k, v in parse_body(ProjectUpdateIn).model_dump(exclude_unset=True).items()
            if v is not None}
    project = project_service.update_project(project, data)
    return jsonify({"project": project_out(project)})


@bp.delete("/<uuid:project_id>")
@doc("Delete a project and its assets permanently", tags=["Projects"])
@login_required
def delete_project(project_id: uuid.UUID):
    project = project_service.get_owned_project(current_user(), project_id)
    project_service.delete_project(project)
    return "", 204


@bp.post("/<uuid:project_id>/duplicate")
@doc("Duplicate a project's text, characters and scenes (not media)", tags=["Projects"])
@login_required
def duplicate_project(project_id: uuid.UUID):
    project = project_service.get_owned_project(current_user(), project_id)
    copy = project_service.duplicate_project(current_user(), project)
    return jsonify({"project": project_out(copy)}), 201


# ---- Characters -------------------------------------------------------------------

@bp.post("/<uuid:project_id>/characters")
@doc("Add a character", tags=["Characters"], body=CharacterIn)
@login_required
def create_character(project_id: uuid.UUID):
    user = current_user()
    project = project_service.get_owned_project(user, project_id)
    character = project_service.create_character(user, project, parse_body(CharacterIn).model_dump())
    return jsonify({"character": character_out(character)}), 201


@bp.patch("/<uuid:project_id>/characters/<uuid:character_id>")
@doc("Update a character", tags=["Characters"], body=CharacterUpdateIn)
@login_required
def update_character(project_id: uuid.UUID, character_id: uuid.UUID):
    user = current_user()
    project = project_service.get_owned_project(user, project_id)
    character = project_service.get_character(project, character_id)
    data = parse_body(CharacterUpdateIn).model_dump(exclude_unset=True)
    data = {k: v for k, v in data.items() if v is not None or k == "reference_asset_id"}
    character = project_service.update_character(user, project, character, data)
    return jsonify({"character": character_out(character)})


@bp.delete("/<uuid:project_id>/characters/<uuid:character_id>")
@doc("Delete a character", tags=["Characters"])
@login_required
def delete_character(project_id: uuid.UUID, character_id: uuid.UUID):
    project = project_service.get_owned_project(current_user(), project_id)
    character = project_service.get_character(project, character_id)
    db.session.delete(character)
    db.session.commit()
    return "", 204


# ---- Scenes (storyboard) -----------------------------------------------------------

@bp.post("/<uuid:project_id>/scenes")
@doc("Add a scene at the end of the storyboard", tags=["Scenes"], body=SceneIn)
@login_required
def create_scene(project_id: uuid.UUID):
    user = current_user()
    project = project_service.get_owned_project(user, project_id)
    scene = project_service.create_scene(user, project, parse_body(SceneIn).model_dump())
    return jsonify({"scene": scene_out(scene)}), 201


@bp.patch("/<uuid:project_id>/scenes/<uuid:scene_id>")
@doc("Update a scene", tags=["Scenes"], body=SceneUpdateIn)
@login_required
def update_scene(project_id: uuid.UUID, scene_id: uuid.UUID):
    user = current_user()
    project = project_service.get_owned_project(user, project_id)
    scene = project_service.get_scene(project, scene_id)
    data = parse_body(SceneUpdateIn).model_dump(exclude_unset=True)
    nullable = {"duration_seconds", "preview_asset_id"}
    data = {k: v for k, v in data.items() if v is not None or k in nullable}
    scene = project_service.update_scene(user, project, scene, data)
    return jsonify({"scene": scene_out(scene)})


@bp.delete("/<uuid:project_id>/scenes/<uuid:scene_id>")
@doc("Delete a scene", tags=["Scenes"])
@login_required
def delete_scene(project_id: uuid.UUID, scene_id: uuid.UUID):
    project = project_service.get_owned_project(current_user(), project_id)
    project_service.delete_scene(project, project_service.get_scene(project, scene_id))
    return "", 204


@bp.put("/<uuid:project_id>/scenes/order")
@doc("Reorder all scenes", tags=["Scenes"], body=SceneOrderIn)
@login_required
def reorder_scenes(project_id: uuid.UUID):
    project = project_service.get_owned_project(current_user(), project_id)
    scenes = project_service.reorder_scenes(project, parse_body(SceneOrderIn).scene_ids)
    return jsonify({"scenes": [scene_out(s) for s in scenes]})


# ---- Project assets and jobs --------------------------------------------------------

@bp.get("/<uuid:project_id>/assets")
@doc("List a project's assets", tags=["Assets"], query={"kind": "image|video|audio|text"})
@login_required
def list_project_assets(project_id: uuid.UUID):
    user = current_user()
    project = project_service.get_owned_project(user, project_id)
    limit, offset = pagination(default_limit=50)
    query = select(Asset).where(Asset.project_id == project.id, Asset.owner_id == user.id)
    kind = request.args.get("kind")
    if kind:
        try:
            query = query.where(Asset.kind == AssetKind(kind))
        except ValueError as exc:
            raise APIError("Unknown asset kind.", code="invalid_filter") from exc
    total = db.session.scalar(select(func.count()).select_from(query.subquery()))
    assets = db.session.scalars(query.order_by(Asset.created_at.desc()).limit(limit).offset(offset)).all()
    return jsonify(page([asset_out(a) for a in assets], total, limit, offset))


@bp.post("/<uuid:project_id>/assets")
@doc("Upload a file to a project (multipart field 'file')", tags=["Assets"], multipart=True)
@login_required
def upload_project_asset(project_id: uuid.UUID):
    user = current_user()
    project = project_service.get_owned_project(user, project_id)
    file = request.files.get("file")
    if file is None:
        raise APIError("Attach the file in a multipart field named 'file'.", code="file_required",
                       status_code=422)
    display_name = (request.form.get("display_name") or "").strip()[:255] or None
    asset = asset_service.save_upload(user, project.id, file.stream, file.filename, display_name)
    return jsonify({"asset": asset_out(asset)}), 201


@bp.get("/<uuid:project_id>/jobs")
@doc("List a project's generation jobs", tags=["Generation"])
@login_required
def list_project_jobs(project_id: uuid.UUID):
    user = current_user()
    project = project_service.get_owned_project(user, project_id)
    limit, offset = pagination()
    query = select(GenerationJob).where(GenerationJob.project_id == project.id,
                                        GenerationJob.user_id == user.id)
    total = db.session.scalar(select(func.count()).select_from(query.subquery()))
    jobs = db.session.scalars(query.order_by(GenerationJob.created_at.desc())
                              .limit(limit).offset(offset)).all()
    return jsonify(page([job_out(j) for j in jobs], total, limit, offset))
