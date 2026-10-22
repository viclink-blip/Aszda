"""AI providers (capabilities) and generation jobs."""

from __future__ import annotations

import uuid
from dataclasses import asdict

from flask import Blueprint, jsonify, request
from sqlalchemy import func, select

from app.api.common import doc, idempotency_key, page, pagination, parse_body
from app.errors import APIError
from app.extensions import db, limiter
from app.models import GenerationJob, GenerationKind, JobStatus
from app.providers import registry
from app.schemas.requests import GenerationIn, QuoteIn
from app.schemas.serializers import job_out
from app.security.auth import current_user, login_required
from app.services import generation_service, pricing

bp = Blueprint("generation", __name__, url_prefix="/api")


def provider_catalog() -> list[dict]:
    catalog = []
    for adapter in registry.all_adapters():
        configured = adapter.is_configured()
        models = []
        for spec in adapter.model_specs():
            price = pricing.price_for(adapter.name, spec.id)
            models.append({
                "id": spec.id, "label": spec.label, "kind": spec.kind.value,
                "description": spec.description,
                "fields": [asdict(f) for f in spec.fields],
                "usage_metrics": spec.usage_metrics,
                "pricing": {"credits_per_1000": price.credits_per_1000,
                            "minimum_credits": price.minimum_credits} if price else None,
                "deprecated": spec.deprecated,
                "shutdown_on": spec.shutdown_on.isoformat() if spec.shutdown_on else None,
                # Usable only when the API key is set, a credit price is configured and the
                # provider has not shut the model down.
                "available": configured and price is not None and not spec.is_retired(),
                "unavailable_reason": (
                    "provider_not_configured" if not configured else
                    "model_retired" if spec.is_retired() else
                    "pricing_not_configured" if price is None else None),
            })
        catalog.append({
            "name": adapter.name, "label": adapter.label, "configured": configured,
            "supports_cancel": adapter.supports_cancel, "models": models,
        })
    return catalog


@bp.get("/providers")
@doc("AI providers, their models, supported settings and availability", tags=["Generation"])
@login_required
def list_providers():
    return jsonify({"providers": provider_catalog()})


@bp.post("/generation-jobs/quote")
@doc("Validate a request and estimate its credits without running it", tags=["Generation"], body=QuoteIn)
@login_required
def quote():
    data = parse_body(QuoteIn)
    return jsonify(generation_service.quote(current_user(), provider=data.provider, model=data.model,
                                            kind=data.kind, params=data.params))


@bp.post("/generation-jobs")
@doc("Start a generation job (requires an Idempotency-Key header)", tags=["Generation"],
     body=GenerationIn)
@login_required
@limiter.limit("20 per minute")
def create_job():
    key = idempotency_key()
    data = parse_body(GenerationIn)
    job, created = generation_service.create_job(
        current_user(), idempotency_key=key, provider=data.provider, model=data.model, kind=data.kind,
        params=data.params, project_id=data.project_id, scene_id=data.scene_id)
    db.session.refresh(job)
    return jsonify({"job": job_out(job)}), 201 if created else 200


@bp.get("/generation-jobs")
@doc("List my generation jobs", tags=["Generation"],
     query={"status": "queued|validating|processing|completed|failed|cancelled",
            "kind": "text|image|video|animation|speech", "project_id": "uuid"})
@login_required
def list_jobs():
    user = current_user()
    limit, offset = pagination()
    query = select(GenerationJob).where(GenerationJob.user_id == user.id)
    try:
        if request.args.get("status"):
            query = query.where(GenerationJob.status == JobStatus(request.args["status"]))
        if request.args.get("kind"):
            query = query.where(GenerationJob.kind == GenerationKind(request.args["kind"]))
        if request.args.get("project_id"):
            query = query.where(GenerationJob.project_id == uuid.UUID(request.args["project_id"]))
    except ValueError as exc:
        raise APIError("Invalid filter.", code="invalid_filter") from exc
    total = db.session.scalar(select(func.count()).select_from(query.subquery()))
    jobs = db.session.scalars(query.order_by(GenerationJob.created_at.desc())
                              .limit(limit).offset(offset)).all()
    return jsonify(page([job_out(j) for j in jobs], total, limit, offset))


@bp.get("/generation-jobs/<uuid:job_id>")
@doc("Get a job's status, progress and result", tags=["Generation"])
@login_required
def get_job(job_id: uuid.UUID):
    return jsonify({"job": job_out(generation_service.get_owned_job(current_user(), job_id))})


@bp.post("/generation-jobs/<uuid:job_id>/cancel")
@doc("Cancel a queued or running job (refunds reserved credits)", tags=["Generation"])
@login_required
def cancel_job(job_id: uuid.UUID):
    job = generation_service.cancel_job(current_user(), job_id)
    return jsonify({"job": job_out(job)})


@bp.post("/generation-jobs/<uuid:job_id>/retry")
@doc("Retry a failed or cancelled job as a new job (requires an Idempotency-Key header)",
     tags=["Generation"])
@login_required
@limiter.limit("20 per minute")
def retry_job(job_id: uuid.UUID):
    key = idempotency_key()
    job, created = generation_service.retry_job(current_user(), job_id, key)
    db.session.refresh(job)
    return jsonify({"job": job_out(job)}), 201 if created else 200
