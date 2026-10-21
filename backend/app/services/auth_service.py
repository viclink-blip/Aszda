"""Registration, sign-in, session rotation, email verification and password reset."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from flask import current_app
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.errors import APIError, Conflict, Unauthorized
from app.extensions import db
from app.models import (
    AuthSession,
    RefreshToken,
    Role,
    TokenPurpose,
    User,
    UserProfile,
    UserToken,
)
from app.security.passwords import (
    hash_password,
    needs_rehash,
    password_problems,
    verify_password,
)
from app.security.tokens import create_access_token, hash_token, new_opaque_token
from app.services import audit, credit_service, email

log = logging.getLogger(__name__)


def now() -> datetime:
    return datetime.now(UTC)


@dataclass
class IssuedSession:
    user: User
    access_token: str
    expires_in: int
    refresh_token: str


def normalize_email(value: str) -> str:
    return value.strip().lower()


def _check_password(password: str, email_addr: str) -> None:
    problems = password_problems(password, email_addr)
    if problems:
        raise APIError("Choose a stronger password.", code="weak_password",
                       status_code=422, details={"problems": problems})


def register(email_addr: str, password: str, display_name: str) -> User:
    email_addr = normalize_email(email_addr)
    _check_password(password, email_addr)

    user = User(email=email_addr, password_hash=hash_password(password), role=Role.USER)
    user.profile = UserProfile(display_name=display_name.strip())
    db.session.add(user)
    try:
        db.session.flush()
    except IntegrityError as exc:
        db.session.rollback()
        raise Conflict("An account with this email already exists.", code="email_taken") from exc

    credit_service.ensure_account(user.id)
    grant = current_app.config["SIGNUP_CREDIT_GRANT"]
    if grant > 0:
        credit_service.grant(user.id, grant, reference=f"signup:{user.id}",
                             reason="Sign-up credit grant", actor_id=None)
    audit.record("user.registered", actor_id=user.id, target_type="user", target_id=user.id)
    token = _issue_user_token(user, TokenPurpose.VERIFY_EMAIL)
    db.session.commit()
    email.send(email.verification_email(user.email, token))
    return user


def authenticate(email_addr: str, password: str) -> User:
    email_addr = normalize_email(email_addr)
    user = db.session.scalar(select(User).where(User.email == email_addr))
    ok = verify_password(user.password_hash if user else None, password)
    if not ok or user is None or not user.is_active:
        audit.record("auth.login_failed", actor_id=user.id if user else None,
                     target_type="user", target_id=user.id if user else None)
        db.session.commit()
        # The same message for every case, so nobody can probe which emails exist.
        raise Unauthorized("Email or password is incorrect.", code="invalid_credentials")
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    return user


def start_session(user: User, user_agent: str | None, ip: str | None) -> IssuedSession:
    session = AuthSession(
        user_id=user.id,
        expires_at=now() + current_app.config["REFRESH_TOKEN_TTL"],
        user_agent=(user_agent or "")[:255] or None,
        ip_address=ip,
    )
    db.session.add(session)
    db.session.flush()
    refresh = _new_refresh_token(session)
    user.last_login_at = now()
    audit.record("auth.login", actor_id=user.id, target_type="session", target_id=session.id)
    db.session.commit()
    access, ttl = create_access_token(user.id, session.id, user.role.value)
    return IssuedSession(user=user, access_token=access, expires_in=ttl, refresh_token=refresh)


def _new_refresh_token(session: AuthSession) -> str:
    raw = new_opaque_token()
    db.session.add(RefreshToken(session_id=session.id, token_hash=hash_token(raw),
                                expires_at=session.expires_at))
    return raw


def rotate_refresh_token(raw_token: str) -> IssuedSession:
    """Exchange a refresh token for a new access token and a new refresh token.

    Each refresh token works once. If an already-used token is presented again,
    someone may have stolen it, so the whole session is revoked.
    """
    token = db.session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token)).with_for_update()
    )
    if token is None:
        raise Unauthorized("Please sign in again.", code="invalid_refresh_token")
    session = db.session.get(AuthSession, token.session_id)
    grace = timedelta(seconds=current_app.config["REFRESH_REUSE_GRACE_SECONDS"])
    if token.used_at is not None and now() - token.used_at > grace:
        if session.revoked_at is None:
            session.revoked_at = now()
            session.revoked_reason = "refresh_token_reuse"
            audit.record("auth.refresh_reuse_detected", actor_id=session.user_id,
                         target_type="session", target_id=session.id)
            db.session.commit()
        raise Unauthorized("Please sign in again.", code="invalid_refresh_token")
    if session.revoked_at is not None or token.expires_at <= now() or session.expires_at <= now():
        raise Unauthorized("Please sign in again.", code="invalid_refresh_token")

    user = db.session.get(User, session.user_id)
    if user is None or not user.is_active:
        raise Unauthorized("This account is not available.", code="account_inactive")

    token.used_at = token.used_at or now()
    new_raw = _new_refresh_token(session)
    db.session.commit()
    access, ttl = create_access_token(user.id, session.id, user.role.value)
    return IssuedSession(user=user, access_token=access, expires_in=ttl, refresh_token=new_raw)


def revoke_session(session_id: uuid.UUID, reason: str) -> None:
    session = db.session.get(AuthSession, session_id)
    if session and session.revoked_at is None:
        session.revoked_at = now()
        session.revoked_reason = reason
    db.session.commit()


def revoke_session_by_refresh_token(raw_token: str) -> None:
    token = db.session.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token)))
    if token is not None:
        revoke_session(token.session_id, "logout")


def revoke_all_sessions(user_id: uuid.UUID, reason: str) -> None:
    db.session.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now(), revoked_reason=reason)
    )


def _issue_user_token(user: User, purpose: TokenPurpose) -> str:
    # Older unused tokens of the same purpose stop working.
    db.session.execute(
        update(UserToken)
        .where(UserToken.user_id == user.id, UserToken.purpose == purpose, UserToken.used_at.is_(None))
        .values(used_at=now())
    )
    ttl = (current_app.config["EMAIL_VERIFICATION_TTL"] if purpose == TokenPurpose.VERIFY_EMAIL
           else current_app.config["PASSWORD_RESET_TTL"])
    raw = new_opaque_token()
    db.session.add(UserToken(user_id=user.id, purpose=purpose, token_hash=hash_token(raw),
                             expires_at=now() + ttl))
    return raw


def _consume_user_token(raw: str, purpose: TokenPurpose) -> User:
    token = db.session.scalar(
        select(UserToken).where(UserToken.token_hash == hash_token(raw), UserToken.purpose == purpose)
        .with_for_update()
    )
    if token is None or token.used_at is not None or token.expires_at <= now():
        raise APIError("This link is invalid or has expired.", code="invalid_token", status_code=400)
    token.used_at = now()
    return db.session.get(User, token.user_id)


def send_verification(user: User) -> None:
    if user.email_verified:
        return
    token = _issue_user_token(user, TokenPurpose.VERIFY_EMAIL)
    db.session.commit()
    email.send(email.verification_email(user.email, token))


def verify_email(raw_token: str) -> User:
    user = _consume_user_token(raw_token, TokenPurpose.VERIFY_EMAIL)
    if user.email_verified_at is None:
        user.email_verified_at = now()
    audit.record("user.email_verified", actor_id=user.id, target_type="user", target_id=user.id)
    db.session.commit()
    return user


def request_password_reset(email_addr: str) -> None:
    user = db.session.scalar(select(User).where(User.email == normalize_email(email_addr)))
    if user is None or not user.is_active:
        return  # Same response either way; do not reveal whether the email exists.
    token = _issue_user_token(user, TokenPurpose.RESET_PASSWORD)
    audit.record("auth.password_reset_requested", actor_id=user.id, target_type="user", target_id=user.id)
    db.session.commit()
    email.send(email.password_reset_email(user.email, token))


def reset_password(raw_token: str, new_password: str) -> None:
    user = _consume_user_token(raw_token, TokenPurpose.RESET_PASSWORD)
    _check_password(new_password, user.email)
    user.password_hash = hash_password(new_password)
    # Receiving the email proves ownership of the address.
    if user.email_verified_at is None:
        user.email_verified_at = now()
    revoke_all_sessions(user.id, "password_reset")
    audit.record("auth.password_reset", actor_id=user.id, target_type="user", target_id=user.id)
    db.session.commit()


def change_password(user: User, current_password: str, new_password: str,
                    keep_session_id: uuid.UUID | None) -> None:
    if not verify_password(user.password_hash, current_password):
        raise APIError("Your current password is incorrect.", code="invalid_password", status_code=400)
    _check_password(new_password, user.email)
    user.password_hash = hash_password(new_password)
    db.session.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None),
               AuthSession.id != keep_session_id)
        .values(revoked_at=now(), revoked_reason="password_changed")
    )
    audit.record("auth.password_changed", actor_id=user.id, target_type="user", target_id=user.id)
    db.session.commit()


def delete_account(user: User, password: str) -> None:
    """Permanently delete the account and everything it owns (see docs/DATA_RETENTION.md)."""
    from app.services import asset_service

    if not verify_password(user.password_hash, password):
        raise APIError("Your password is incorrect.", code="invalid_password", status_code=400)
    user_id = user.id
    keys = asset_service.storage_keys_for_owner(user_id)
    audit.record("user.deleted", actor_id=None, target_type="user", target_id=user_id)
    db.session.delete(user)
    db.session.commit()
    asset_service.delete_storage_objects(keys)
