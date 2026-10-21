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
