"""Access tokens (short-lived JWT) and opaque random tokens (refresh, email links)."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime

import jwt
from flask import current_app

ISSUER = "aszda"
ALGORITHM = "HS256"


def new_opaque_token() -> str:
    """A random, URL-safe token with 256 bits of entropy."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Tokens are stored as SHA-256 hashes so a database leak cannot be replayed."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(user_id: uuid.UUID, session_id: uuid.UUID, role: str) -> tuple[str, int]:
    now = datetime.now(UTC)
    ttl = current_app.config["ACCESS_TOKEN_TTL"]
    payload = {
        "iss": ISSUER,
        "sub": str(user_id),
        "sid": str(session_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + ttl,
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm=ALGORITHM)
    return token, int(ttl.total_seconds())


def decode_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError when the token is invalid or expired."""
    payload = jwt.decode(
        token,
        current_app.config["JWT_SECRET_KEY"],
        algorithms=[ALGORITHM],
        issuer=ISSUER,
        options={"require": ["exp", "iat", "sub", "sid", "type"]},
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("wrong token type")
    return payload
