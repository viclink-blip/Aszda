"""Generation jobs: create (with idempotency, limits and credit reservation), run,
poll, finish, fail, cancel and retry.

Credit rules (also in docs/CREDITS.md):
1. Before a job is queued, its estimated maximum cost is RESERVED from the balance.
2. On success the actual cost is charged (never more than reserved) and the rest is RELEASED.
3. On failure or cancellation the reservation is REFUNDED, except for usage the
   provider reports it actually billed (for example a refused text request).
4. Each of these ledger entries has a unique reference per job, so a retried task
   can never charge or refund twice.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from flask import current_app
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from app.errors import APIError, Conflict, NotFound, ServiceUnavailable
from app.extensions import db
from app.models import (
    ACTIVE_STATUSES,
    Asset,
    CreditAccount,
    GenerationJob,
    GenerationKind,
    JobStatus,
    Project,
    ProviderCost,
    Scene,
    User,
)
from app.models.generation import TRANSITIONS
from app.providers import registry
from app.providers.base import JobContext, ProviderAdapter, ProviderError, ProviderOutcome
from app.services import asset_service, audit, credit_service, orchestrator, pricing
from app.storage.backends import get_storage

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


def now() -> datetime:
    return datetime.now(UTC)


class InvalidTransition(RuntimeError):
    pass


def _transition(job: GenerationJob, new_status: JobStatus) -> None:
    if new_status not in TRANSITIONS[job.status]:
        raise InvalidTransition(f"{job.status.value} -> {new_status.value}")
    job.status = new_status


# ---- Creating jobs -------------------------------------------------------------

def fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _existing_job(user: User, idempotency_key: str) -> GenerationJob | None:
    return db.session.scalar(select(GenerationJob).where(
        GenerationJob.user_id == user.id, GenerationJob.idempotency_key == idempotency_key))


def _resolve_adapter(provider: str | None, model: str | None, kind: GenerationKind):
    """The adapter, model and routing record for a request (see services/orchestrator.py)."""
    chosen = orchestrator.route(kind, provider, model)
    return chosen.adapter, chosen.spec, chosen


MAX_CONVERSATION_TURNS = 40          # 20 exchanges
MAX_CONVERSATION_CHARS = 150_000


def _with_conversation(user: User, params: dict[str, Any], provider: str, kind: GenerationKind) -> dict[str, Any]:
    """Follow-up messages: rebuild the earlier conversation from the user's own completed job.

    The browser only names the job it continues (`continue_from_job_id`); it can never send
    the history itself, so nobody can put words in the model's mouth or read another user's
    conversation. The oldest exchanges are dropped when the conversation gets long."""
    if "history" in params:
        raise APIError("The conversation history is filled in by the server.", code="invalid_params",
                       status_code=422)
    raw = params.get("continue_from_job_id")
    if not raw:
        return params
    try:
        previous = db.session.get(GenerationJob, uuid.UUID(str(raw)))
    except ValueError as exc:
        raise APIError("Invalid conversation reference.", code="invalid_params", status_code=422) from exc
    if previous is None or previous.user_id != user.id:
        raise NotFound("The answer you are replying to was not found.")
    text = (previous.result or {}).get("text")
    if (kind != GenerationKind.TEXT or previous.kind != GenerationKind.TEXT or previous.provider != provider
            or previous.status != JobStatus.COMPLETED or not text
            or (previous.input_params or {}).get("task") == "director_plan"):
        raise Conflict("Only a finished text answer from the same provider can be continued.",
                       code="cannot_continue")
    history = list(previous.input_params.get("history") or []) + [
        {"role": "user", "content": previous.input_params["prompt"]},
        {"role": "assistant", "content": text[:100_000]}]
    while len(history) > MAX_CONVERSATION_TURNS or sum(len(t["content"]) for t in history) > MAX_CONVERSATION_CHARS:
        history = history[2:]  # drop the oldest question and answer together
    return {**params, "history": history}


def _check_referenced_assets(user: User, params: dict[str, Any], project_id: uuid.UUID | None) -> None:
    for key, value in params.items():
        if key.endswith("asset_id") and value:
            asset = asset_service.get_owned_asset(user, uuid.UUID(str(value)))
            if project_id and asset.project_id not in (None, project_id):
                raise APIError("That asset belongs to a different project.",
                               code="asset_not_in_project", status_code=422)


def _check_limits(user: User, cost: int) -> None:
    cfg = current_app.config
    if cost > cfg["MAX_CREDITS_PER_JOB"]:
        raise APIError(f"This request would cost {cost} credits; the limit per job is "
                       f"{cfg['MAX_CREDITS_PER_JOB']}. Try a shorter or smaller request.",
                       code="job_too_expensive", status_code=422,
                       details={"estimated_credits": cost, "limit": cfg["MAX_CREDITS_PER_JOB"]})
    active = db.session.scalar(select(func.count()).select_from(GenerationJob).where(
        GenerationJob.user_id == user.id, GenerationJob.status.in_(ACTIVE_STATUSES)))
    if active >= cfg["MAX_ACTIVE_JOBS_PER_USER"]:
        raise APIError(f"You already have {active} generations running. Wait for one to finish.",
                       code="too_many_active_jobs", status_code=429)
    day_start = now().replace(hour=0, minute=0, second=0, microsecond=0)
    today = db.session.scalar(select(func.count()).select_from(GenerationJob).where(
        GenerationJob.user_id == user.id, GenerationJob.created_at >= day_start))
    if today >= cfg["DAILY_JOB_LIMIT"]:
        raise APIError("You reached today's generation limit. It resets at midnight UTC.",
                       code="daily_limit_reached", status_code=429)
    month_start = day_start.replace(day=1)
    # Settled jobs count what they were charged (0 for most failures); running jobs count
    # their reservation.
    spent = db.session.scalar(select(func.coalesce(func.sum(
        func.coalesce(GenerationJob.credits_charged, GenerationJob.credits_reserved)), 0)).where(
        GenerationJob.user_id == user.id, GenerationJob.created_at >= month_start))
    limit = monthly_limit_for(user)
    if spent + cost > limit:
        raise APIError("This request would go over your monthly usage limit.",
                       code="monthly_limit_reached", status_code=429,
                       details={"used_this_month": spent, "limit": limit})


def monthly_limit_for(user: User) -> int:
    """The plan's admin-set monthly limit when the user has an active plan, else the global one."""
    from app.billing.catalog import monthly_credit_limit_for
    from app.models import Subscription, SubscriptionStatus

    sub = db.session.scalar(select(Subscription).where(Subscription.user_id == user.id))
    if sub is not None and sub.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.NON_RENEWING,
                                          SubscriptionStatus.PAST_DUE):
        plan_limit = monthly_credit_limit_for(sub.plan_code)
        if plan_limit:
            return plan_limit
    return current_app.config["MONTHLY_CREDIT_LIMIT"]


def quote(user: User, *, provider: str | None, model: str | None, kind: GenerationKind,
          params: dict[str, Any]) -> dict[str, Any]:
    """Validate a request and return its credit estimate without creating a job."""
    adapter, spec, chosen = _resolve_adapter(provider, model, kind)
    params = _with_conversation(user, params, adapter.name, kind)
    clean = adapter.validate(spec, params)
    usage = adapter.estimate_usage(spec, clean)
    price = pricing.price_for(adapter.name, spec.id)
    balance = credit_service.get_account(user.id).balance
    db.session.commit()
    return {
        "priced": price is not None,
        "estimated_credits": price.credits_for(usage) if price else None,
        "estimated_usage": usage,
        "balance": balance,
        "provider": adapter.name,
        "model": spec.id,
        "fallback_used": chosen.fallback_used,
    }


def create_job(user: User, *, idempotency_key: str, provider: str | None, model: str | None,
               kind: GenerationKind,
               params: dict[str, Any], project_id: uuid.UUID | None, scene_id: uuid.UUID | None,
               retry_of: GenerationJob | None = None) -> tuple[GenerationJob, bool]:
    """Returns (job, created). created is False when the idempotency key was seen before."""
    request_fp = fingerprint({"provider": provider, "model": model, "kind": kind.value,
                              "params": params, "project_id": project_id, "scene_id": scene_id,
                              "retry_of": retry_of.id if retry_of else None})
    existing = _existing_job(user, idempotency_key)
    if existing is not None:
        if existing.request_fingerprint != request_fp:
            raise Conflict("This Idempotency-Key was already used for a different request.",
                           code="idempotency_key_reused")
        return existing, False

    if current_app.config["REQUIRE_VERIFIED_EMAIL_FOR_GENERATION"] and not user.email_verified:
        raise APIError("Confirm your email address before generating.", code="email_not_verified",
                       status_code=403)

    if project_id is not None:
        project = db.session.get(Project, project_id)
        if project is None or project.owner_id != user.id:
            raise NotFound("Project not found.")
    if scene_id is not None:
        scene = db.session.get(Scene, scene_id)
        if scene is None or scene.project_id != project_id:
            raise NotFound("Scene not found in this project.")

    adapter, spec, chosen = _resolve_adapter(provider, model, kind)
    if retry_of is None:  # a retry re-uses the conversation its original job already had
        params = _with_conversation(user, params, adapter.name, kind)
    clean = adapter.validate(spec, params)
    _check_referenced_assets(user, clean, project_id)
    provider, model = adapter.name, spec.id

    price = pricing.price_for(provider, model)  # checked by the orchestrator; read once here
    estimate = adapter.estimate_usage(spec, clean)
    cost = price.credits_for(estimate)

    # Lock the user's credit account: this serialises job creation per user, so
    # the limit checks and the reservation below cannot race each other.
    credit_service.ensure_account(user.id)
    db.session.execute(select(CreditAccount).where(CreditAccount.user_id == user.id).with_for_update())
    # Look again now that we hold the lock: a parallel duplicate may have committed meanwhile.
    # Returning it here (instead of inserting and hitting the unique key) also avoids a
    # deadlock: that insert would wait on the job row a worker is settling, while the worker
    # waits for the account lock held here.
    existing = _existing_job(user, idempotency_key)
    if existing is not None:
        db.session.rollback()
        if existing.request_fingerprint != request_fp:
            raise Conflict("This Idempotency-Key was already used for a different request.",
                           code="idempotency_key_reused")
        return existing, False
    _check_limits(user, cost)

    job = GenerationJob(
        id=uuid.uuid4(), user_id=user.id, project_id=project_id, scene_id=scene_id,
        retry_of_id=retry_of.id if retry_of else None, idempotency_key=idempotency_key,
        request_fingerprint=request_fp, kind=kind, provider=provider, model=model,
        input_params=clean, status=JobStatus.QUEUED, credits_reserved=cost,
        usage={"estimate": estimate, "routing": chosen.record(), "pricing": {
            "credits_per_1000": price.credits_per_1000, "minimum_credits": price.minimum_credits,
            "provider_usd_per_1000": price.provider_usd_per_1000 or {}}},
    )
    db.session.add(job)
    try:
        db.session.flush()
        credit_service.reserve_for_job(user.id, job.id, cost)
        db.session.commit()
    except IntegrityError:
        # Two identical requests raced; the other one won. Return its job.
        db.session.rollback()
        existing = _existing_job(user, idempotency_key)
        if existing is None:
            raise
        return existing, False
    except Exception:
        db.session.rollback()
        raise

    _enqueue_run(job)
    return job, True


def _enqueue_run(job: GenerationJob, countdown: int = 0) -> None:
    from app.tasks.generation import run_generation_job

    try:
        result = run_generation_job.apply_async(args=[str(job.id)], countdown=countdown)
    except Exception as exc:  # noqa: BLE001 — broker down: fail the job and refund now
        log.exception("Could not queue job %s", job.id)
        locked = _lock_job(job.id)
        if locked.status == JobStatus.QUEUED:
            _fail(locked, ProviderError("The job queue is unavailable. Your credits were returned.",
                                        code="queue_unavailable"))
        raise ServiceUnavailable("The generation queue is unavailable. Please try again shortly.",
                                 code="queue_unavailable") from exc
    if not current_app.config.get("CELERY_TASK_ALWAYS_EAGER"):
        db.session.refresh(job)
        if job.task_id is None:
            job.task_id = result.id
            db.session.commit()


_eager = threading.local()


def _enqueue_poll(job: GenerationJob) -> None:
    from app.tasks.generation import poll_generation_job

    interval = current_app.config["PROVIDER_POLL_INTERVAL_SECONDS"]
    if not current_app.config.get("CELERY_TASK_ALWAYS_EAGER"):
        poll_generation_job.apply_async(args=[str(job.id)], countdown=interval)
        return
    # Eager mode (development/tests): Celery would run the poll immediately and
    # recursively. Poll in a loop with a real pause instead.
    pending = getattr(_eager, "polls", None)
    if pending is not None:
        pending.append(job.id)
        return
    _eager.polls = [job.id]
    try:
        while _eager.polls:
            job_id = _eager.polls.pop(0)
            if interval:
                time.sleep(interval)
            poll_job(job_id)
    finally:
        _eager.polls = None


# ---- Running jobs (called from Celery tasks) ----------------------------------

def _lock_job(job_id: uuid.UUID) -> GenerationJob:
    db.session.rollback()  # start from a fresh transaction
    return db.session.scalar(
        select(GenerationJob).where(GenerationJob.id == job_id).with_for_update()
        .execution_options(populate_existing=True))


def _context(job: GenerationJob) -> JobContext:
    def load_asset(asset_id: uuid.UUID) -> tuple[bytes, str]:
        asset = db.session.get(Asset, asset_id)
        if asset is None or asset.owner_id != job.user_id:
            raise ProviderError("A referenced asset no longer exists.", code="missing_asset")
        with get_storage().open(asset.storage_key) as fh:
            return fh.read(), asset.mime_type

    return JobContext(job_id=job.id, model=job.model, params=dict(job.input_params),
                      provider_job_id=job.provider_job_id, load_asset=load_asset)


def run_job(job_id: uuid.UUID) -> None:
    job = _lock_job(job_id)
    if job is None or job.status != JobStatus.QUEUED:
        db.session.rollback()
        return  # already handled (duplicate delivery or cancelled)
    _transition(job, JobStatus.VALIDATING)
    job.attempts += 1
    job.started_at = job.started_at or now()
    db.session.commit()

    adapter = registry.get_adapter(job.provider)
    spec = adapter.get_model(job.model) if adapter else None
    if adapter is None or spec is None or not adapter.is_configured() \
            or orchestrator.provider_disabled(job.provider) or spec.is_retired():
        _fail(_lock_job(job_id), ProviderError("This provider is no longer available.",
                                               code="provider_not_configured"))
        return
    try:
        adapter.validate(spec, job.input_params)
    except Exception as exc:  # noqa: BLE001
        _fail(_lock_job(job_id), ProviderError(f"The request is no longer valid: {exc}",
                                               code="invalid_request"))
        return

    job = _lock_job(job_id)
    if job.status != JobStatus.VALIDATING:
        db.session.rollback()
        return  # cancelled while validating
    _transition(job, JobStatus.PROCESSING)
    db.session.commit()

    try:
        # The DB lock is released here: provider calls can take minutes.
        outcome = adapter.submit(_context(job))
    except ProviderError as exc:
        _handle_error(job_id, exc, may_retry=True)
        return
    except Exception:  # noqa: BLE001
        log.exception("Provider %s crashed on job %s", job.provider, job_id)
        _handle_error(job_id, ProviderError("The provider failed unexpectedly.",
                                            code="provider_error"), may_retry=False)
        return
    _handle_outcome(job_id, adapter, outcome)


def poll_job(job_id: uuid.UUID) -> None:
    job = db.session.get(GenerationJob, job_id)
    if job is None or job.status != JobStatus.PROCESSING or not job.provider_job_id:
        return
    adapter = registry.get_adapter(job.provider)
    deadline = (job.submitted_at or job.created_at) + timedelta(
        minutes=current_app.config["PROVIDER_MAX_POLL_MINUTES"])
    if now() > deadline:
        _try_provider_cancel(adapter, job)
        _fail(_lock_job(job_id), ProviderError("The provider took too long. Your credits were returned.",
                                               code="provider_timeout"))
        return
    try:
        outcome = adapter.poll(_context(job))
    except ProviderError as exc:
        if exc.retryable:
            _enqueue_poll(job)  # temporary problem talking to the provider; try again later
            return
        _handle_error(job_id, exc, may_retry=False)
        return
    _handle_outcome(job_id, adapter, outcome)


def _handle_outcome(job_id: uuid.UUID, adapter: ProviderAdapter, outcome: ProviderOutcome) -> None:
    if outcome.status == "pending":
        job = _lock_job(job_id)
        if job.status != JobStatus.PROCESSING:
            # Cancelled by the user meanwhile: stop the provider work if we can.
            db.session.rollback()
            if outcome.provider_job_id and adapter.supports_cancel:
                job.provider_job_id = outcome.provider_job_id
                _try_provider_cancel(adapter, job)
            return
        if outcome.provider_job_id and job.provider_job_id is None:
            job.provider_job_id = outcome.provider_job_id
            job.submitted_at = now()
        job.progress = outcome.progress
        db.session.commit()
        _enqueue_poll(job)
        return
    _complete(job_id, outcome)


def _complete(job_id: uuid.UUID, outcome: ProviderOutcome) -> None:
    job = db.session.get(GenerationJob, job_id)
    stored: list[Asset] = []
    try:
        for output in outcome.outputs:
            data = output.data if output.data is not None else output.open_stream()
            stored.append(asset_service.save_generated(
                owner_id=job.user_id, project_id=job.project_id, job_id=job.id, data=data,
                mime_type=output.mime_type, kind=output.kind, display_name=output.display_name,
                duration_seconds=output.duration_seconds, width=output.width, height=output.height,
                provider=job.provider, model=job.model))
        keys = [a.storage_key for a in stored]
        db.session.flush()
        asset_ids = [str(a.id) for a in stored]
    except ProviderError as exc:
        db.session.rollback()
        asset_service.delete_storage_objects([a.storage_key for a in stored])
        _handle_error(job_id, exc, may_retry=False)
        return

    pending_assets = [(a.id, a) for a in stored]
    db.session.commit()  # assets are saved; now settle the job under a lock

    job = _lock_job(job_id)
    if job.status != JobStatus.PROCESSING:
        # Cancelled while we were downloading: discard the outputs.
        for asset_id, _ in pending_assets:
            asset = db.session.get(Asset, asset_id)
            if asset:
                db.session.delete(asset)
        db.session.commit()
        asset_service.delete_storage_objects(keys)
        return

    price = pricing.ModelPrice(**job.usage["pricing"])
    charged = min(job.credits_reserved, price.credits_for(outcome.usage)) if outcome.usage else job.credits_reserved
    _transition(job, JobStatus.COMPLETED)
    job.progress = 100
    job.completed_at = now()
    job.result = {**(outcome.result or {}), "asset_ids": asset_ids}
    job.usage = {**job.usage, "actual": outcome.usage}
    if job.scene_id and job.kind == GenerationKind.IMAGE and asset_ids:
        scene = db.session.get(Scene, job.scene_id)
        if scene is not None and scene.preview_asset_id is None:
            scene.preview_asset_id = uuid.UUID(asset_ids[0])  # first image becomes the storyboard frame
    _settle(job, charged, success=True)
    _record_provider_cost(job, "completed", outcome.usage or job.usage.get("estimate") or {},
                          reported=(outcome.result or {}).get("provider_reported"), absorbed=False)
    db.session.commit()


def _handle_error(job_id: uuid.UUID, exc: ProviderError, *, may_retry: bool) -> None:
    job = _lock_job(job_id)
    if job.status != JobStatus.PROCESSING:
        db.session.rollback()
        return
    # Retry only when nothing reached the provider, so a retry cannot be billed twice.
    if may_retry and exc.retryable and job.provider_job_id is None and job.attempts < MAX_ATTEMPTS:
        _transition(job, JobStatus.QUEUED)
        job.error_code = exc.code
        job.error_message = f"Retrying after a temporary problem: {exc.message}"
        db.session.commit()
        _enqueue_run(job, countdown=min(300, 15 * 2 ** job.attempts))
        return
    _fail(job, exc)


def _fail(job: GenerationJob, exc: ProviderError) -> None:
    """Mark a locked job as failed and refund what was not actually used."""
    charged = 0
    if exc.usage:
        price = pricing.ModelPrice(**job.usage["pricing"])
        charged = min(job.credits_reserved, price.credits_for(exc.usage))
        job.usage = {**job.usage, "actual": exc.usage}
    _transition(job, JobStatus.FAILED)
    job.completed_at = now()
    job.error_code = exc.code
    job.error_message = exc.message
    _settle(job, charged, success=False)
    if exc.absorbed_usage:
        # The provider billed ASZDA, the customer is refunded: record it as ASZDA's cost.
        job.usage = {**job.usage, "provider_billed": exc.absorbed_usage}
        _record_provider_cost(job, "safety_blocked" if exc.code == "content_refused" else "failed_billed",
                              exc.absorbed_usage, reported=exc.provider_reported, absorbed=True)
    elif exc.usage:
        _record_provider_cost(job, "failed_billed", exc.usage, reported=exc.provider_reported, absorbed=False)
    db.session.commit()


def _settle(job: GenerationJob, charged: int, *, success: bool) -> None:
    if job.credits_settled_at is not None:
        return
    credit_service.settle_job(job.user_id, job.id, job.credits_reserved, charged, success=success)
    job.credits_charged = charged
    job.credits_settled_at = now()


def _record_provider_cost(job: GenerationJob, outcome: str, usage: dict, *, reported: dict | None,
                          absorbed: bool) -> None:
    """Write ASZDA's provider cost for a job once (unique reference; repeats are ignored)."""
    snapshot = (job.usage or {}).get("pricing") or {}
    usd = pricing.ModelPrice(**snapshot).provider_usd_for(usage) if snapshot else None
    db.session.execute(insert(ProviderCost).values(
        id=uuid.uuid4(), reference=f"job:{job.id}:provider_cost", generation_job_id=job.id,
        user_id=job.user_id, provider=job.provider, model=job.model, outcome=outcome, usage=usage,
        estimated_usd=Decimal(str(usd)) if usd is not None else None, provider_reported=reported or None,
        credits_charged_to_customer=job.credits_charged or 0, absorbed_by_aszda=absorbed,
    ).on_conflict_do_nothing(index_elements=["reference"]))
    if absorbed:
        audit.record("generation.provider_cost_absorbed", actor_id=None, target_type="generation_job",
                     target_id=job.id, outcome=outcome, usage=usage,
                     estimated_usd=str(usd) if usd is not None else None)


def _try_provider_cancel(adapter: ProviderAdapter | None, job: GenerationJob) -> bool:
    if adapter is None or not adapter.supports_cancel or not job.provider_job_id:
        return False
    try:
        return adapter.cancel(_context(job))
    except ProviderError:
        log.warning("Provider cancel failed for job %s", job.id, exc_info=True)
        return False


# ---- User actions ------------------------------------------------------------------

def get_owned_job(user: User, job_id: uuid.UUID) -> GenerationJob:
    job = db.session.get(GenerationJob, job_id)
    if job is None or job.user_id != user.id:
        raise NotFound("Generation job not found.")
    return job


def cancel_job(user: User, job_id: uuid.UUID) -> GenerationJob:
    job = get_owned_job(user, job_id)
    job = _lock_job(job.id)
    if job.status in (JobStatus.QUEUED, JobStatus.VALIDATING):
        pass
    elif job.status == JobStatus.PROCESSING:
        adapter = registry.get_adapter(job.provider)
        if not (adapter and adapter.supports_cancel and job.provider_job_id):
            db.session.rollback()
            raise Conflict("This job is already running at the provider and cannot be cancelled.",
                           code="not_cancellable")
        if not _try_provider_cancel(adapter, job):
            db.session.rollback()
            raise Conflict("The provider did not accept the cancellation. Try again.",
                           code="cancel_failed")
    else:
        db.session.rollback()
        raise Conflict("Only queued or running jobs can be cancelled.", code="not_cancellable")
    _transition(job, JobStatus.CANCELLED)
    job.completed_at = now()
    _settle(job, 0, success=False)
    db.session.commit()
    return job


def retry_job(user: User, job_id: uuid.UUID, idempotency_key: str) -> tuple[GenerationJob, bool]:
    job = get_owned_job(user, job_id)
    if job.status not in (JobStatus.FAILED, JobStatus.CANCELLED):
        raise Conflict("Only failed or cancelled jobs can be retried.", code="not_retryable")
    if job.error_code == "content_refused":
        raise Conflict("This request was declined by the provider; change it before trying again.",
                       code="not_retryable")
    return create_job(user, idempotency_key=idempotency_key, provider=job.provider, model=job.model,
                      kind=job.kind, params=job.input_params, project_id=job.project_id,
                      scene_id=job.scene_id, retry_of=job)


# ---- Recovering stuck jobs ----------------------------------------------------------------

def reap_stuck_jobs() -> dict[str, int]:
    """Find jobs whose worker or queue message was lost and settle them, so reserved credits
    never stay locked forever. Runs every few minutes (Celery beat) or via
    `flask --app wsgi aszda reap-stuck-jobs`. Safe to run any number of times."""
    cfg = current_app.config
    counts = {"failed_queued": 0, "failed_lost_worker": 0, "repolled": 0}
    queued_cutoff = now() - timedelta(minutes=cfg["STUCK_QUEUED_MINUTES"])
    running_cutoff = now() - timedelta(minutes=cfg["STUCK_RUNNING_MINUTES"])
    poll_cutoff = now() - timedelta(seconds=cfg["PROVIDER_POLL_INTERVAL_SECONDS"] * 3 + 300)

    candidates = db.session.scalars(select(GenerationJob.id).where(
        GenerationJob.status.in_(ACTIVE_STATUSES), GenerationJob.updated_at < max(queued_cutoff, poll_cutoff))).all()
    for job_id in candidates:
        job = _lock_job(job_id)
        if job is None or job.status not in ACTIVE_STATUSES:
            db.session.rollback()
            continue
        if job.status == JobStatus.QUEUED and job.updated_at < queued_cutoff:
            _fail(job, ProviderError("The job waited too long in the queue. Your credits were returned.",
                                     code="queue_timeout"))
            counts["failed_queued"] += 1
        elif job.status in (JobStatus.VALIDATING, JobStatus.PROCESSING) and not job.provider_job_id \
                and job.updated_at < running_cutoff:
            _fail(job, ProviderError("The job stopped unexpectedly. Your credits were returned.",
                                     code="worker_lost"))
            counts["failed_lost_worker"] += 1
        elif job.status == JobStatus.PROCESSING and job.provider_job_id and job.updated_at < poll_cutoff:
            db.session.rollback()
            poll_job(job_id)  # resumes polling; past the deadline it cancels and refunds
            counts["repolled"] += 1
        else:
            db.session.rollback()
    return counts
