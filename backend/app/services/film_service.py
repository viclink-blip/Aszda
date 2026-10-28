"""Automatic films: one click turns a story into a finished video.

The steps are the AI Film Director's, run without the user clicking each one:
  1. Claude plans the characters and scenes (a text job), and the plan is added to the project;
  2. ASZDA checks the balance covers the whole film (else it waits for credits);
  3. for every scene: the image, then a video that starts from that image, and the voice;
  4. the clips and voices are joined into one video (film_assembly), saved to the project.

Every generation is an ordinary job made through director_service.generate_scene, so credits
are reserved first and refunded on failure, and job limits still apply. Job creation uses
idempotency keys derived from the film and scene, so advancing twice never starts a job twice.

advance() is driven by job completion (job_finished) and, as a safety net, by Celery beat
(advance_active). It is safe to call at any time.
"""

from __future__ import annotations

import contextvars
import logging
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select, text

from app.errors import APIError, Conflict
from app.extensions import db
from app.models import (
    ACTIVE_FILM_STATUSES,
    FINAL_STATUSES,
    Asset,
    AssetKind,
    FilmProduction,
    FilmStatus,
    GenerationJob,
    JobStatus,
    Project,
    Scene,
    User,
)
from app.services import credit_service, director_service, orchestrator, pricing

log = logging.getLogger(__name__)

KINDS = ("image", "video", "voice")
# A pass that hits one of these stops starting jobs; the film waits and continues later.
WAIT_CODES = {"too_many_active_jobs"}
# These pause the film until the user adds credits or the limit resets, then clicks Continue.
PAUSE_CODES = {"insufficient_credits", "monthly_limit_reached", "daily_limit_reached"}

# Set while advance() runs, so jobs finishing inside it (eager mode) do not start a nested run;
# the running advance() picks up their results itself.
_advancing: contextvars.ContextVar[bool] = contextvars.ContextVar("film_advancing", default=False)


def now() -> datetime:
    return datetime.now(UTC)


# ---- Starting, continuing, cancelling ---------------------------------------------------------

def active_film(project_id: uuid.UUID) -> FilmProduction | None:
    return db.session.scalar(select(FilmProduction).where(
        FilmProduction.project_id == project_id, FilmProduction.status.in_(ACTIVE_FILM_STATUSES)))


def _existing(user: User, project: Project, idempotency_key: str) -> FilmProduction | None:
    existing = db.session.scalar(select(FilmProduction).where(
        FilmProduction.user_id == user.id, FilmProduction.idempotency_key == idempotency_key))
    if existing is None and active_film(project.id) is not None:
        raise Conflict("A film is already being made in this project. Wait for it to finish or stop it.",
                       code="film_in_progress")
    return existing


def _entry(scene: Scene, orientation: str, *, reuse: bool) -> dict[str, Any]:
    """A scene's place in the film. With reuse, pictures, videos and voices this scene already has
    are used instead of being made (and paid for) again."""
    entry: dict[str, Any] = {"scene_id": str(scene.id)}
    skipped: dict[str, str] = {}
    if not director_service._brief(scene, "voice", orientation)["text"]:
        skipped["voice"] = "This scene has no narration or dialogue."
    if reuse:
        for kind in KINDS:
            if kind in skipped:
                continue
            job_id = db.session.scalar(
                select(GenerationJob.id).where(
                    GenerationJob.scene_id == scene.id,
                    GenerationJob.kind == director_service.SCENE_KINDS[kind],
                    GenerationJob.status == JobStatus.COMPLETED)
                .order_by(GenerationJob.completed_at.desc()).limit(1))
            if job_id is not None:
                entry[f"{kind}_job_id"] = str(job_id)
        if "image_job_id" not in entry and scene.preview_asset_id is not None:
            skipped["image"] = "Uses the scene's existing picture."
    if skipped:
        entry["skipped"] = skipped
    return entry


def start_film_from_scenes(user: User, project: Project, *, orientation: str,
                           idempotency_key: str) -> tuple[FilmProduction, bool]:
    """Make the film from the scenes the project already has: no new plan, and anything a scene
    already has (its picture, video or voice) is reused."""
    existing = _existing(user, project, idempotency_key)
    if existing is not None:
        return existing, False
    scenes = db.session.scalars(select(Scene).where(Scene.project_id == project.id).order_by(Scene.position)).all()
    if not scenes:
        raise Conflict("This project has no scenes yet. Plan the film first.", code="no_scenes")
    film = FilmProduction(user_id=user.id, project_id=project.id, idempotency_key=idempotency_key,
                          status=FilmStatus.PLANNING, plan_job_id=None,
                          options={"orientation": orientation, "from_scenes": True},
                          scenes=[_entry(s, orientation, reuse=True) for s in scenes])
    db.session.add(film)
    db.session.commit()
    schedule(film.id)
    return film, True


def start_film(user: User, project: Project, *, idea: str, orientation: str, effort: str,
               idempotency_key: str) -> tuple[FilmProduction, bool]:
    existing = _existing(user, project, idempotency_key)
    if existing is not None:
        return existing, False
    plan_job, _ = director_service.start_plan(
        user, project, idea=idea, idempotency_key=f"film:{idempotency_key}:plan"[:128], provider=None,
        model=None, max_output_tokens=16000, effort=effort)
    film = FilmProduction(user_id=user.id, project_id=project.id, idempotency_key=idempotency_key,
                          status=FilmStatus.PLANNING, plan_job_id=plan_job.id,
                          options={"orientation": orientation}, scenes=[])
    db.session.add(film)
    db.session.commit()
    schedule(film.id)
    return film, True


def resume(user: User, film: FilmProduction) -> FilmProduction:
    if film.status != FilmStatus.WAITING_FOR_CREDITS:
        raise Conflict("This film is not waiting.", code="film_not_waiting")
    film.status = FilmStatus.PRODUCING if film.scenes else FilmStatus.PLANNING
    film.error_code = film.error_message = None
    db.session.commit()
    schedule(film.id)
    return film


def cancel(user: User, film: FilmProduction) -> FilmProduction:
    """Stop starting new steps. Jobs already running finish normally (and are charged as usual)."""
    if film.status not in ACTIVE_FILM_STATUSES:
        raise Conflict("This film has already finished.", code="film_finished")
    film.status = FilmStatus.CANCELLED
    film.completed_at = now()
    db.session.commit()
    return film


def get_owned(user: User, film_id: uuid.UUID) -> FilmProduction:
    from app.errors import NotFound

    film = db.session.get(FilmProduction, film_id)
    if film is None or film.user_id != user.id:
        raise NotFound("Film not found.")
    return film


def latest_for_project(project_id: uuid.UUID) -> FilmProduction | None:
    return db.session.scalar(select(FilmProduction).where(FilmProduction.project_id == project_id)
                             .order_by(FilmProduction.created_at.desc()).limit(1))


# ---- Triggers --------------------------------------------------------------------------------

def schedule(film_id: uuid.UUID) -> None:
    if _advancing.get():
        return
    from app.tasks.generation import advance_film

    advance_film.delay(str(film_id))


def job_finished(job: GenerationJob) -> None:
    """Called when any job reaches a final state: wake the film it belongs to, if any."""
    if job.project_id is None or _advancing.get():
        return
    film = active_film(job.project_id)
    if film is not None and film.status in (FilmStatus.PLANNING, FilmStatus.PRODUCING):
        schedule(film.id)


def advance_active() -> int:
    """Safety net (Celery beat): move every unfinished film along."""
    ids = db.session.scalars(select(FilmProduction.id).where(
        FilmProduction.status.in_((FilmStatus.PLANNING, FilmStatus.PRODUCING, FilmStatus.ASSEMBLING)))).all()
    for film_id in ids:
        advance(film_id)
    return len(ids)


# ---- The state machine ------------------------------------------------------------------------

def advance(film_id: uuid.UUID) -> None:
    # A PostgreSQL advisory lock on its own connection (job creation commits, which would end a
    # row lock). If another worker is already advancing this film, it will see the news itself.
    lock_conn = db.engine.connect()
    try:
        got = lock_conn.execute(text("SELECT pg_try_advisory_lock(hashtextextended(:k, 0))"),
                                {"k": f"film:{film_id}"}).scalar()
        if not got:
            return
        token = _advancing.set(True)
        try:
            for _ in range(50):  # each pass either makes progress or stops
                if not _step(film_id):
                    break
        finally:
            _advancing.reset(token)
            lock_conn.execute(text("SELECT pg_advisory_unlock(hashtextextended(:k, 0))"), {"k": f"film:{film_id}"})
    finally:
        lock_conn.close()


def _step(film_id: uuid.UUID) -> bool:
    """One pass. Returns True when something changed and another pass may do more."""
    db.session.expire_all()
    film = db.session.get(FilmProduction, film_id)
    if film is None:
        return False
    if film.status == FilmStatus.PLANNING:
        return _after_plan(film)
    if film.status == FilmStatus.PRODUCING:
        return _produce(film)
    if film.status == FilmStatus.ASSEMBLING:
        # Joining happens in the same pass that sets ASSEMBLING, under the advisory lock; finding
        # it here means that worker stopped part-way, so join again.
        return _assemble(film)
    return False


def _fail(film: FilmProduction, code: str, message: str) -> bool:
    film.status = FilmStatus.FAILED
    film.error_code, film.error_message = code, message[:500]
    film.completed_at = now()
    db.session.commit()
    return False


def _pause(film: FilmProduction, code: str, message: str) -> bool:
    film.status = FilmStatus.WAITING_FOR_CREDITS
    film.error_code, film.error_message = code, message[:500]
    db.session.commit()
    return False


def _after_plan(film: FilmProduction) -> bool:
    if film.plan_job_id is None and film.scenes:
        return _check_budget(film, already_paid=0)  # made from the project's existing scenes
    job = db.session.get(GenerationJob, film.plan_job_id) if film.plan_job_id else None
    if job is None:
        return _fail(film, "plan_missing", "The film plan could not be found.")
    if job.status not in FINAL_STATUSES:
        return False
    if job.status != JobStatus.COMPLETED or not (job.result or {}).get("plan"):
        return _fail(film, "plan_failed", "The story could not be planned, so no scenes were made. "
                     "Your credits for the plan were returned.")
    user = db.session.get(User, film.user_id)
    project = db.session.get(Project, film.project_id)
    if not film.scenes:
        applied = list((project.brief or {}).get("director_applied_jobs", []))
        if str(job.id) in applied:
            # Applied in an earlier pass that did not finish: find its scenes again.
            scenes = db.session.scalars(select(Scene).where(Scene.project_id == project.id).order_by(
                Scene.position)).all()
            scenes = [s for s in scenes if (s.ai_prompts or {}).get("plan_job_id") == str(job.id)]
        else:
            scenes = director_service.apply_plan(user, project, job.id)
        orientation = film.options.get("orientation", "landscape")
        film.scenes = [_entry(s, orientation, reuse=False) for s in scenes]
        db.session.commit()
    if not film.scenes:
        return _fail(film, "plan_empty", "The plan had no scenes.")
    return _check_budget(film, already_paid=job.credits_charged or 0)


def _check_budget(film: FilmProduction, *, already_paid: int) -> bool:
    user = db.session.get(User, film.user_id)
    estimate, missing = _estimate(user, film)
    if "video" in missing:
        return _fail(film, "no_video_provider", "No video provider is set up, so the film cannot be made.")
    # The whole film: what was already paid (the plan), plus an upper bound for every remaining step.
    film.estimated_credits = already_paid + estimate
    balance = credit_service.get_account(user.id).balance
    if balance < estimate:  # anything already paid for is not counted again
        return _pause(film, "insufficient_credits",
                      f"The rest of this film needs about {estimate:,} credits and you have {balance:,}. "
                      "Add credits, then click Continue.")
    film.status = FilmStatus.PRODUCING
    db.session.commit()
    return True


def _route_ready(kind: str):
    try:
        return orchestrator.route(director_service.SCENE_KINDS[kind], None)
    except APIError:
        return None


def _estimate(user: User, film: FilmProduction) -> tuple[int, set[str]]:
    """Credits for every image, video and voice still to make (an upper bound, like a reservation)."""
    total, missing = 0, set()
    orientation = film.options.get("orientation", "landscape")
    for kind in KINDS:
        chosen = _route_ready(kind)
        if chosen is None:
            missing.add(kind)
            continue
        price = pricing.price_for(chosen.adapter.name, chosen.spec.id)
        for entry in film.scenes:
            if entry.get(f"{kind}_job_id") or kind in (entry.get("skipped") or {}):
                continue  # already made, or not needed
            scene = db.session.get(Scene, uuid.UUID(entry["scene_id"]))
            if scene is None:
                continue
            brief = director_service._brief(scene, kind, orientation)
            if (kind == "voice" and not brief["text"]) or (kind != "voice" and not brief["prompt"]):
                continue
            params = chosen.adapter.params_for_brief(chosen.spec, brief)
            try:
                clean = chosen.adapter.validate(chosen.spec, {k: v for k, v in params.items() if v is not None})
            except ValidationError:
                continue  # this step fails clearly when it is started; nothing to reserve for it
            if price is not None:
                total += price.credits_for(chosen.adapter.estimate_usage(chosen.spec, clean))
    return total, missing


def _job_state(job_id: str | None) -> str | None:
    if not job_id:
        return None
    job = db.session.get(GenerationJob, uuid.UUID(job_id))
    if job is None:
        return "failed"
    if job.status == JobStatus.COMPLETED:
        return "completed"
    return "failed" if job.status in FINAL_STATUSES else "active"


def _kind_done(entry: dict, kind: str) -> bool:
    if kind in (entry.get("skipped") or {}) or kind in (entry.get("errors") or {}):
        return True
    return _job_state(entry.get(f"{kind}_job_id")) in ("completed", "failed")


def _produce(film: FilmProduction) -> bool:
    user = db.session.get(User, film.user_id)
    project = db.session.get(Project, film.project_id)
    orientation = film.options.get("orientation", "landscape")
    ready = {kind: _route_ready(kind) is not None for kind in KINDS}
    scenes = [dict(e) for e in film.scenes]
    changed = False

    def start(entry: dict, kind: str) -> str | None:
        """Start one step. Returns a code when the film must wait or pause."""
        nonlocal changed
        if not ready[kind]:
            entry.setdefault("skipped", {})[kind] = "No provider is set up for this."
            changed = True
            return None
        try:
            result = director_service.generate_scene(
                user, project, uuid.UUID(entry["scene_id"]), kinds=[kind], providers={},
                orientation=orientation, idempotency_key=f"film:{film.id}:{entry['scene_id']}")[0]
        except APIError as exc:  # e.g. the scene was deleted
            result = {"error": {"code": exc.code, "message": exc.message}}
        if result.get("job_id"):
            entry[f"{kind}_job_id"] = result["job_id"]
            changed = True
        elif result.get("skipped"):
            entry.setdefault("skipped", {})[kind] = result["skipped"]
            changed = True
        else:
            error = result.get("error") or {}
            code = error.get("code") or "error"
            if code in WAIT_CODES or code in PAUSE_CODES:
                return code
            entry.setdefault("errors", {})[kind] = error.get("message") or "Could not start."
            changed = True
        return None

    blocked: str | None = None
    for entry in scenes:
        if blocked:
            break
        # Image and voice can start at once; the video waits for the image (its first frame).
        for kind in ("image", "voice"):
            if not blocked and not entry.get(f"{kind}_job_id") and not _kind_done(entry, kind):
                blocked = start(entry, kind)
        if not blocked and not entry.get("video_job_id") and not _kind_done(entry, "video") \
                and _kind_done(entry, "image"):
            blocked = start(entry, "video")

    film.scenes = scenes
    db.session.commit()
    if blocked in PAUSE_CODES:
        messages = {"insufficient_credits": "You ran out of credits. Add credits, then click Continue.",
                    "monthly_limit_reached": "Your monthly usage limit was reached.",
                    "daily_limit_reached": "Today's generation limit was reached. Click Continue tomorrow."}
        return _pause(film, blocked, messages[blocked])
    if all(_kind_done(e, k) for e in scenes for k in KINDS):
        if not any(_job_state(e.get("video_job_id")) == "completed" for e in scenes):
            return _fail(film, "no_clips", "No scene video could be made, so there is no film to join. "
                         "Credits for failed steps were returned.")
        film.status = FilmStatus.ASSEMBLING
        db.session.commit()
        return _assemble(film)
    return changed


def _assemble(film: FilmProduction) -> bool:
    from app.services import asset_service, film_assembly
    from app.storage.backends import get_storage

    project = db.session.get(Project, film.project_id)
    segments, temp_dir = [], tempfile.TemporaryDirectory(prefix="aszda-film-")
    try:
        work = Path(temp_dir.name)

        def fetch(job_id: str | None, index: int, kind: str) -> Path | None:
            if _job_state(job_id) != "completed":
                return None
            job = db.session.get(GenerationJob, uuid.UUID(job_id))
            asset_ids = (job.result or {}).get("asset_ids") or []
            asset = db.session.get(Asset, uuid.UUID(asset_ids[0])) if asset_ids else None
            if asset is None:
                return None
            path = work / f"{index:03d}-{kind}"
            with get_storage().open(asset.storage_key) as src, open(path, "wb") as dst:
                while chunk := src.read(1024 * 1024):
                    dst.write(chunk)
            return path

        for index, entry in enumerate(film.scenes):
            video = fetch(entry.get("video_job_id"), index, "video")
            if video is not None:
                segments.append(film_assembly.Segment(video=video, audio=fetch(entry.get("voice_job_id"), index,
                                                                                "voice")))
        try:
            output, duration = film_assembly.join(segments, work / "film.mp4",
                                                  portrait=film.options.get("orientation") == "portrait")
        except film_assembly.AssemblyError as exc:
            log.warning("Film %s could not be joined: %s", film.id, exc)
            return _fail(film, "assembly_failed", "The scenes were made, but joining them into one film "
                         "failed. Every clip and voice is in the project's Assets.")
        with open(output, "rb") as fh:
            asset = asset_service.save_generated(
                owner_id=film.user_id, project_id=film.project_id, job_id=None, data=fh,
                mime_type="video/mp4", kind=AssetKind.VIDEO, display_name=f"{project.title} - full film",
                duration_seconds=duration, provider="aszda", model="film-assembly")
        film.film_asset_id = asset.id
        film.status = FilmStatus.COMPLETED
        film.completed_at = now()
        film.error_code = film.error_message = None
        db.session.commit()
        return False
    finally:
        temp_dir.cleanup()


# ---- Output ----------------------------------------------------------------------------------

def film_out(film: FilmProduction) -> dict[str, Any]:
    from app.schemas.serializers import asset_out, iso

    job_ids = [uuid.UUID(e[f"{k}_job_id"]) for e in film.scenes for k in KINDS if e.get(f"{k}_job_id")]
    if film.plan_job_id:
        job_ids.append(film.plan_job_id)
    jobs = {j.id: j for j in db.session.scalars(select(GenerationJob).where(GenerationJob.id.in_(job_ids)))} \
        if job_ids else {}
    scene_rows = {s.id: s for s in db.session.scalars(select(Scene).where(
        Scene.id.in_([uuid.UUID(e["scene_id"]) for e in film.scenes])))} if film.scenes else {}

    def step(entry: dict, kind: str) -> dict[str, Any]:
        if kind in (entry.get("skipped") or {}):
            return {"state": "skipped", "message": entry["skipped"][kind]}
        if kind in (entry.get("errors") or {}):
            return {"state": "failed", "message": entry["errors"][kind]}
        job = jobs.get(uuid.UUID(entry[f"{kind}_job_id"])) if entry.get(f"{kind}_job_id") else None
        if job is None:
            return {"state": "waiting"}
        state = {JobStatus.COMPLETED: "done"}.get(job.status, "failed" if job.status in FINAL_STATUSES else "running")
        out = {"state": state, "job_id": str(job.id)}
        if state == "failed" and job.error_message:
            out["message"] = job.error_message
        if state == "done" and (job.result or {}).get("asset_ids"):
            out["asset_id"] = job.result["asset_ids"][0]
        return out

    scenes = []
    for entry in film.scenes:
        scene = scene_rows.get(uuid.UUID(entry["scene_id"]))
        scenes.append({"scene_id": entry["scene_id"], "title": scene.title if scene else "Deleted scene",
                       **{kind: step(entry, kind) for kind in KINDS}})
    counts = {kind: {"done": sum(1 for s in scenes if s[kind]["state"] == "done"),
                     "total": sum(1 for s in scenes if s[kind]["state"] != "skipped")} for kind in KINDS}
    plan_job = jobs.get(film.plan_job_id) if film.plan_job_id else None
    film_asset = db.session.get(Asset, film.film_asset_id) if film.film_asset_id else None
    charged = sum(j.credits_charged or 0 for j in jobs.values())
    return {
        "id": str(film.id), "project_id": str(film.project_id), "status": film.status.value,
        "orientation": film.options.get("orientation", "landscape"),
        "plan_job_id": str(film.plan_job_id) if film.plan_job_id else None,
        "plan_status": plan_job.status.value if plan_job else None,
        "estimated_credits": film.estimated_credits, "credits_charged": charged,
        "scenes": scenes, "counts": counts,
        "film_asset": asset_out(film_asset) if film_asset else None,
        "error": {"code": film.error_code, "message": film.error_message} if film.error_code else None,
        "created_at": iso(film.created_at), "completed_at": iso(film.completed_at),
    }
