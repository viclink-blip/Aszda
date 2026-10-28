"""Background tasks for generation jobs. The logic lives in generation_service."""

from __future__ import annotations

import uuid

from app.tasks.celery_app import celery


@celery.task(name="aszda.run_generation_job")
def run_generation_job(job_id: str) -> None:
    from app.services import generation_service

    generation_service.run_job(uuid.UUID(job_id))


@celery.task(name="aszda.poll_generation_job")
def poll_generation_job(job_id: str) -> None:
    from app.services import generation_service

    generation_service.poll_job(uuid.UUID(job_id))


@celery.task(name="aszda.advance_film")
def advance_film(film_id: str) -> None:
    from app.services import film_service

    film_service.advance(uuid.UUID(film_id))


@celery.task(name="aszda.advance_active_films")
def advance_active_films() -> int:
    from app.services import film_service

    return film_service.advance_active()


@celery.task(name="aszda.reap_stuck_jobs")
def reap_stuck_jobs() -> dict:
    from app.services import generation_service

    return generation_service.reap_stuck_jobs()


@celery.task(name="aszda.expire_subscriptions")
def expire_subscriptions() -> int:
    from app.services.payment_service import expire_overdue_subscriptions

    return expire_overdue_subscriptions()
