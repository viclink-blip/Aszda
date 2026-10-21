"""ASZDA Studio API — application factory."""

from __future__ import annotations

import logging

from flask import Flask
from flask_cors import CORS

from app.config import get_config
from app.errors import register_error_handlers
from app.extensions import db, limiter, migrate
from app.security.headers import register_security_headers
from app.tasks.celery_app import init_celery


def create_app(config_name: str | None = None) -> Flask:
    config = get_config(config_name)
    problems = config.validate()
    if problems:
        raise RuntimeError("Configuration problems:\n- " + "\n- ".join(problems))

    app = Flask(__name__)
    app.config.from_object(config)
    logging.basicConfig(level=app.config["LOG_LEVEL"],
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    from app import models  # noqa: F401 — registers models for migrations

    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)
    # The web app normally calls the API through its own origin (a reverse proxy
    # or Next.js rewrite). CORS is only opened to the configured origins.
    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
         supports_credentials=True, allow_headers=["Authorization", "Content-Type",
                                                   "Idempotency-Key", "X-Requested-With"])
    init_celery(app)
    register_error_handlers(app)
    register_security_headers(app)

    from app.api import register_blueprints

    register_blueprints(app)

    from app.cli import register_cli

    register_cli(app)
    return app
