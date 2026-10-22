"""Celery, configured from the Flask app so tasks run with the app's config and database."""

from __future__ import annotations

from celery import Celery, Task
from flask import Flask, has_app_context

celery = Celery("aszda")


def init_celery(app: Flask) -> Celery:
    class FlaskTask(Task):
        def __call__(self, *args, **kwargs):
            if has_app_context():
                return self.run(*args, **kwargs)
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.conf.update(
        broker_url=app.config["CELERY_BROKER_URL"],
        result_backend=app.config["CELERY_RESULT_BACKEND"],
        task_always_eager=app.config["CELERY_TASK_ALWAYS_EAGER"],
        task_eager_propagates=True,
        task_ignore_result=True,
        # A task is acknowledged only after it finishes, so a crashed worker's job
        # is delivered again. Our tasks are idempotent, so that is safe.
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        broker_connection_retry_on_startup=True,
        task_default_queue="aszda",
        timezone="UTC",
        # Periodic housekeeping (needs one process running Celery beat, e.g. `worker -B`).
        beat_schedule={
            "reap-stuck-jobs": {"task": "aszda.reap_stuck_jobs", "schedule": 300.0},
            "expire-subscriptions": {"task": "aszda.expire_subscriptions", "schedule": 3600.0},
        },
    )
    celery.Task = FlaskTask
    celery.set_default()
    app.extensions["celery"] = celery
    return celery
