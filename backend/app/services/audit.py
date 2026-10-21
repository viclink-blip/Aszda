"""Write audit events. Callers commit the surrounding transaction."""

from __future__ import annotations

import uuid
from typing import Any

from flask import has_request_context, request

from app.extensions import db
from app.models import AuditEvent


def record(action: str, *, actor_id: uuid.UUID | None = None, target_type: str | None = None,
           target_id: Any = None, **details: Any) -> AuditEvent:
    event = AuditEvent(
        actor_user_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        ip_address=request.remote_addr if has_request_context() else None,
        details=details,
    )
    db.session.add(event)
    return event
