"""Projects, characters and scenes. Every lookup is scoped to the requesting user."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select

from app.errors import APIError, NotFound
from app.extensions import db
from app.models import Asset, Character, Project, ProjectStatus, Scene, User
from app.services import asset_service


def get_owned_project(user: User, project_id: uuid.UUID) -> Project:
    project = db.session.get(Project, project_id)
    # Collaboration (ProjectMember) is not implemented yet: only the owner has access.
    if project is None or project.owner_id != user.id:
        raise NotFound("Project not found.")
    return project


def list_projects(user: User, *, status: ProjectStatus | None, search: str | None,
                  limit: int, offset: int) -> tuple[list[Project], int]:
    query = select(Project).where(Project.owner_id == user.id)
    if status:
        query = query.where(Project.status == status)
    if search:
        pattern = f"%{search.replace('%', r'\%').replace('_', r'\_')}%"
        query = query.where(Project.title.ilike(pattern, escape="\\"))
    total = db.session.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.session.scalars(query.order_by(Project.updated_at.desc()).limit(limit).offset(offset)).all()
    return list(rows), total


def create_project(user: User, data: dict[str, Any]) -> Project:
    project = Project(owner_id=user.id, **data)
    db.session.add(project)
    db.session.commit()
    return project


def update_project(project: Project, data: dict[str, Any]) -> Project:
    for key, value in data.items():
        setattr(project, key, value)
    db.session.commit()
    return project


def delete_project(project: Project) -> None:
    keys = asset_service.storage_keys_for_project(project.id)
    db.session.delete(project)
    db.session.commit()
    asset_service.delete_storage_objects(keys)


def duplicate_project(user: User, project: Project) -> Project:
    """Copy the project's text, characters and scenes. Media assets are not copied
    (they would double storage costs); the copy starts without assets."""
    copy = Project(owner_id=user.id, title=f"{project.title} (copy)"[:120],
                   description=project.description, brief=dict(project.brief),
                   status=ProjectStatus.DRAFT)
    db.session.add(copy)
    db.session.flush()
    char_map: dict[uuid.UUID, Character] = {}
    for ch in project.characters:
        new = Character(project_id=copy.id, name=ch.name, description=ch.description, traits=dict(ch.traits))
        db.session.add(new)
        char_map[ch.id] = new
    for sc in project.scenes:
        db.session.add(Scene(
            project_id=copy.id, position=sc.position, title=sc.title, description=sc.description,
            shot_notes=sc.shot_notes, dialogue=sc.dialogue, duration_seconds=sc.duration_seconds,
            characters=[char_map[c.id] for c in sc.characters if c.id in char_map],
        ))
    db.session.commit()
    return copy


def project_stats(project_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, int]]:
    if not project_ids:
        return {}
    stats = {pid: {"asset_count": 0, "scene_count": 0, "character_count": 0} for pid in project_ids}
    for model, name in ((Asset, "asset_count"), (Scene, "scene_count"), (Character, "character_count")):
        rows = db.session.execute(
            select(model.project_id, func.count()).where(model.project_id.in_(project_ids))
            .group_by(model.project_id)
        )
        for pid, count in rows:
            stats[pid][name] = count
    return stats


# ---- Characters --------------------------------------------------------------

def get_character(project: Project, character_id: uuid.UUID) -> Character:
    character = db.session.get(Character, character_id)
    if character is None or character.project_id != project.id:
        raise NotFound("Character not found.")
    return character


def _check_reference_asset(user: User, project: Project, asset_id: uuid.UUID | None) -> None:
    if asset_id is None:
        return
    asset = asset_service.get_owned_asset(user, asset_id)
    if asset.project_id not in (None, project.id):
        raise APIError("That asset belongs to a different project.", code="asset_not_in_project",
                       status_code=422)


def create_character(user: User, project: Project, data: dict[str, Any]) -> Character:
    _check_reference_asset(user, project, data.get("reference_asset_id"))
    character = Character(project_id=project.id, **data)
    db.session.add(character)
    db.session.commit()
    return character


def update_character(user: User, project: Project, character: Character, data: dict[str, Any]) -> Character:
    if "reference_asset_id" in data:
        _check_reference_asset(user, project, data["reference_asset_id"])
    for key, value in data.items():
        setattr(character, key, value)
    db.session.commit()
    return character


# ---- Scenes ------------------------------------------------------------------

def get_scene(project: Project, scene_id: uuid.UUID) -> Scene:
    scene = db.session.get(Scene, scene_id)
    if scene is None or scene.project_id != project.id:
        raise NotFound("Scene not found.")
    return scene


def _characters_for(project: Project, ids: list[uuid.UUID]) -> list[Character]:
    if not ids:
        return []
    found = db.session.scalars(
        select(Character).where(Character.project_id == project.id, Character.id.in_(ids))
    ).all()
    if len(found) != len(set(ids)):
        raise APIError("One or more characters are not part of this project.",
                       code="character_not_in_project", status_code=422)
    return list(found)


def create_scene(user: User, project: Project, data: dict[str, Any]) -> Scene:
    character_ids = data.pop("character_ids", []) or []
    _check_reference_asset(user, project, data.get("preview_asset_id"))
    next_position = db.session.scalar(
        select(func.coalesce(func.max(Scene.position) + 1, 0)).where(Scene.project_id == project.id)
    )
    scene = Scene(project_id=project.id, position=next_position, **data)
    scene.characters = _characters_for(project, character_ids)
    db.session.add(scene)
    db.session.commit()
    return scene


def update_scene(user: User, project: Project, scene: Scene, data: dict[str, Any]) -> Scene:
    if "character_ids" in data:
        scene.characters = _characters_for(project, data.pop("character_ids") or [])
    if "preview_asset_id" in data:
        _check_reference_asset(user, project, data["preview_asset_id"])
    for key, value in data.items():
        setattr(scene, key, value)
    db.session.commit()
    return scene


def delete_scene(project: Project, scene: Scene) -> None:
    db.session.delete(scene)
    db.session.flush()
    _compact_positions(project)
    db.session.commit()


def reorder_scenes(project: Project, scene_ids: list[uuid.UUID]) -> list[Scene]:
    scenes = {s.id: s for s in db.session.scalars(select(Scene).where(Scene.project_id == project.id))}
    if set(scene_ids) != set(scenes) or len(scene_ids) != len(scenes):
        raise APIError("Send every scene of the project exactly once.", code="invalid_order",
                       status_code=422)
    # The unique (project_id, position) constraint is deferred, so swaps are fine.
    for index, sid in enumerate(scene_ids):
        scenes[sid].position = index
    db.session.commit()
    return [scenes[sid] for sid in scene_ids]


def _compact_positions(project: Project) -> None:
    ordered = db.session.scalars(
        select(Scene).where(Scene.project_id == project.id).order_by(Scene.position)
    ).all()
    for index, scene in enumerate(ordered):
        scene.position = index
