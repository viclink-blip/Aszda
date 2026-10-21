"""Health checks for load balancers and monitoring."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from app.api.common import doc
from app.extensions import db, limiter

bp = Blueprint("health", __name__, url_prefix="/api/health")


@bp.get("")
@doc("Liveness: the API process is running", tags=["Health"], auth="none")
@limiter.exempt
def live():
    return jsonify({"status": "ok", "service": "aszda-api"})


@bp.get("/ready")
@doc("Readiness: database and queue are reachable", tags=["Health"], auth="none")
@limiter.exempt
def ready():
    checks = {}
    try:
        db.session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:  # noqa: BLE001
        checks["database"] = "unavailable"
    if current_app.config.get("CELERY_TASK_ALWAYS_EAGER"):
        checks["queue"] = "eager"
    else:
        try:
            import redis

            redis.Redis.from_url(current_app.config["CELERY_BROKER_URL"], socket_timeout=2).ping()
            checks["queue"] = "ok"
        except Exception:  # noqa: BLE001
            checks["queue"] = "unavailable"
    healthy = all(v in ("ok", "eager") for v in checks.values())
    return jsonify({"status": "ok" if healthy else "degraded", "checks": checks}), 200 if healthy else 503
