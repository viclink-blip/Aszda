"""Celery worker entry point.

    celery -A celery_worker.celery worker --loglevel=info -Q aszda
"""

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402
from app.tasks import generation  # noqa: E402,F401 — registers the tasks
from app.tasks.celery_app import celery  # noqa: E402,F401

flask_app = create_app()
