"""The AI Film Director: plan a film with Claude, add the plan to a project, then generate
each scene's image, video and voice with the configured providers."""

from __future__ import annotations

import uuid
from typing import Literal

from flask import Blueprint, jsonify
from pydantic import Field, field_validator

from app.api.common import doc, idempotency_key, parse_body
from app.extensions import db, limiter
from app.schemas.requests import Strict
from app.schemas.serializers import job_out, scene_out
from app.security.auth import current_user, login_required
from app.services import director_service, project_service

bp = Blueprint("director", __name__, url_prefix="/api/projects/<uuid:project_id>/director")


class PlanIn(Strict):
    idea: str = Field(min_length=10, max_length=10000)
    provider: str | None = Field(default=None, min_length=1, max_length=50)
    model: str | None = Field(default=None, min_length=1, max_length=100)
    max_output_tokens: int = Field(default=12000, ge=2000, le=16000)
    effort: Literal["low", "medium", "high"] = "medium"


class ApplyIn(Strict):
    job_id: uuid.UUID


class SceneGenerateIn(Strict):
    kinds: list[Literal["image", "video", "voice"]] = Field(min_length=1, max_length=3)
    # Optional explicit provider per kind, e.g. {"video": "google"}; otherwise the configured one.
    providers: dict[Literal["image", "video", "voice"], str] = Field(default_factory=dict)
    orientation: Literal["landscape", "portrait"] = "landscape"

    @field_validator("kinds")
    @classmethod
    def unique(cls, v):
        if len(set(v)) != len(v):
            raise ValueError("List each kind once.")
        return v


@bp.post("/plan")
@doc("Ask Claude for a film plan (characters and scenes). Costs credits like any text job; "
     "requires an Idempotency-Key header", tags=["Director"], body=PlanIn)
@login_required
@limiter.limit("10 per minute")
def plan(project_id: uuid.UUID):
    user = current_user()
    project = project_service.get_owned_project(user, project_id)
    data = parse_body(PlanIn)
    job, created = director_service.start_plan(
        user, project, idea=data.idea, idempotency_key=idempotency_key(), provider=data.provider,
        model=data.model, max_output_tokens=data.max_output_tokens, effort=data.effort)
    db.session.refresh(job)
    return jsonify({"job": job_out(job)}), 201 if created else 200


@bp.post("/apply")
@doc("Add a finished plan's characters and scenes to the project (once per plan)", tags=["Director"],
     body=ApplyIn)
@login_required
def apply(project_id: uuid.UUID):
    user = current_user()
    project = project_service.get_owned_project(user, project_id)
    scenes = director_service.apply_plan(user, project, parse_body(ApplyIn).job_id)
    return jsonify({"scenes": [scene_out(s) for s in scenes]}), 201


@bp.post("/scenes/<uuid:scene_id>/generate")
@doc("Generate a scene's image, video and/or voice with the configured providers (one job per kind; "
     "requires an Idempotency-Key header)", tags=["Director"], body=SceneGenerateIn)
@login_required
@limiter.limit("20 per minute")
def generate(project_id: uuid.UUID, scene_id: uuid.UUID):
    user = current_user()
    project = project_service.get_owned_project(user, project_id)
    data = parse_body(SceneGenerateIn)
    results = director_service.generate_scene(
        user, project, scene_id, kinds=list(data.kinds), providers=dict(data.providers),
        orientation=data.orientation, idempotency_key=idempotency_key())
    return jsonify({"results": results}), 202
