"""Request authentication and authorization decorators.

Usage:
    @bp.get("/projects")
    @login_required
    def list_projects(): ...

    @bp.get("/admin/users")
    @admin_required
    def list_users(): ...
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from functools import wraps

import jwt
from flask import g, request

from app.errors import Forbidden, Unauthorized
from app.extensions import db
from app.models import AuthSession, User
from app.security.tokens import decode_access_token


def _load_user_from_request() -> User:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise Unauthorized("Sign in to continue.", code="not_authenticated")
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError as exc:
        raise Unauthorized("Your session expired. Please refresh.", code="token_expired") from exc
    except jwt.PyJWTError as exc:
        raise Unauthorized("Invalid access token.", code="invalid_token") from exc

    try:
        user_id = uuid.UUID(payload["sub"])
        session_id = uuid.UUID(payload["sid"])
    except (ValueError, KeyError) as exc:
        raise Unauthorized("Invalid access token.", code="invalid_token") from exc

    # Checking the session on every request lets sign-out and "sign out
    # everywhere" take effect immediately instead of waiting for token expiry.
    session = db.session.get(AuthSession, session_id)
    if (session is None or session.user_id != user_id or session.revoked_at is not None
            or session.expires_at <= datetime.now(UTC)):
        raise Unauthorized("Your session has ended. Please sign in again.", code="session_revoked")

    user = db.session.get(User, user_id)
    if user is None or not user.is_active:
        raise Unauthorized("This account is not available.", code="account_inactive")

    g.current_session = session
    return user


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        g.current_user = _load_user_from_request()
        return view(*args, **kwargs)

    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = _load_user_from_request()
        g.current_user = user
        if not user.is_admin:
            raise Forbidden("Administrator access is required.")
        return view(*args, **kwargs)

    return wrapper


def current_user() -> User:
    return g.current_user


def client_ip() -> str | None:
    # Behind a reverse proxy, configure ProxyFix (see wsgi.py) so this is the real client IP.
    return request.remote_addr
