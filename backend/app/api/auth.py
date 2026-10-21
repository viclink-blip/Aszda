"""Authentication endpoints.

Session design:
- Sign-in returns a short-lived access token (JSON) that the web app keeps in
  memory and sends as `Authorization: Bearer <token>`.
- It also sets a long-lived refresh token in an HttpOnly, SameSite=Strict cookie
  scoped to /api/auth, which JavaScript cannot read.
- /api/auth/refresh swaps the refresh cookie for a new access token AND a new
  refresh cookie (rotation). Reusing an old refresh token revokes the session.
- Cookie-authenticated endpoints also require the `X-Requested-With: aszda`
  header. Browsers will not send custom headers cross-site without a CORS
  preflight that we do not allow, which blocks CSRF.
"""

from __future__ import annotations

from flask import Blueprint, current_app, g, jsonify, make_response, request

from app.api.common import doc, parse_body
from app.errors import Forbidden, Unauthorized
from app.extensions import limiter
from app.schemas.requests import EmailIn, LoginIn, RegisterIn, ResetPasswordIn, TokenIn
from app.schemas.serializers import user_out
from app.security.auth import client_ip, current_user, login_required
from app.services import auth_service

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

CSRF_HEADER = "X-Requested-With"
CSRF_VALUE = "aszda"


def _require_csrf_header() -> None:
    if request.headers.get(CSRF_HEADER) != CSRF_VALUE:
        raise Forbidden("Missing request header.", code="csrf_check_failed")


def _session_response(issued: auth_service.IssuedSession, status: int = 200):
    response = make_response(jsonify({
        "access_token": issued.access_token,
        "token_type": "Bearer",
        "expires_in": issued.expires_in,
        "user": user_out(issued.user),
    }), status)
    cfg = current_app.config
    response.set_cookie(
        cfg["REFRESH_COOKIE_NAME"], issued.refresh_token,
        max_age=int(cfg["REFRESH_TOKEN_TTL"].total_seconds()), path=cfg["REFRESH_COOKIE_PATH"],
        secure=cfg["COOKIE_SECURE"], httponly=True, samesite="Strict",
    )
    return response


def _clear_cookie(response):
    cfg = current_app.config
    response.delete_cookie(cfg["REFRESH_COOKIE_NAME"], path=cfg["REFRESH_COOKIE_PATH"],
                           secure=cfg["COOKIE_SECURE"], httponly=True, samesite="Strict")
    return response


@bp.post("/register")
@doc("Create an account and sign in", tags=["Auth"], body=RegisterIn, auth="none")
@limiter.limit("5 per minute; 30 per day", key_func=lambda: f"ip:{request.remote_addr}")
def register():
    data = parse_body(RegisterIn)
    user = auth_service.register(data.email, data.password, data.display_name)
    issued = auth_service.start_session(user, request.user_agent.string, client_ip())
    return _session_response(issued, 201)


@bp.post("/login")
@doc("Sign in with email and password", tags=["Auth"], body=LoginIn, auth="none")
@limiter.limit("10 per minute", key_func=lambda: f"ip:{request.remote_addr}")
@limiter.limit("20 per hour", key_func=lambda: "login:" + str((request.get_json(silent=True) or {})
                                                                .get("email", "")).strip().lower())
def login():
    data = parse_body(LoginIn)
    user = auth_service.authenticate(data.email, data.password)
    issued = auth_service.start_session(user, request.user_agent.string, client_ip())
    return _session_response(issued)


@bp.post("/refresh")
@doc("Get a new access token using the refresh cookie", tags=["Auth"], auth="refresh_cookie")
@limiter.limit("60 per minute", key_func=lambda: f"ip:{request.remote_addr}")
def refresh():
    _require_csrf_header()
    raw = request.cookies.get(current_app.config["REFRESH_COOKIE_NAME"])
    if not raw:
        raise Unauthorized("Please sign in.", code="not_authenticated")
    try:
        issued = auth_service.rotate_refresh_token(raw)
    except Unauthorized as exc:
        response = make_response(jsonify({"error": {"code": exc.code, "message": exc.message}}), 401)
        return _clear_cookie(response)
    return _session_response(issued)


@bp.post("/logout")
@doc("Sign out of this device", tags=["Auth"], auth="refresh_cookie")
def logout():
    _require_csrf_header()
    raw = request.cookies.get(current_app.config["REFRESH_COOKIE_NAME"])
    if raw:
        auth_service.revoke_session_by_refresh_token(raw)
    return _clear_cookie(make_response("", 204))


@bp.post("/logout-all")
@doc("Sign out of every device", tags=["Auth"])
@login_required
def logout_all():
    auth_service.revoke_all_sessions(current_user().id, "logout_all")
    from app.extensions import db

    db.session.commit()
    return _clear_cookie(make_response("", 204))


@bp.post("/verify-email")
@doc("Confirm an email address with the token from the email", tags=["Auth"], body=TokenIn, auth="none")
@limiter.limit("20 per hour", key_func=lambda: f"ip:{request.remote_addr}")
def verify_email():
    data = parse_body(TokenIn)
    user = auth_service.verify_email(data.token)
    return jsonify({"user": user_out(user)})


@bp.post("/resend-verification")
@doc("Send the verification email again", tags=["Auth"])
@login_required
@limiter.limit("3 per hour")
def resend_verification():
    auth_service.send_verification(current_user())
    return "", 202


@bp.post("/password-reset/request")
@doc("Email a password reset link (always returns 202)", tags=["Auth"], body=EmailIn, auth="none")
@limiter.limit("5 per hour", key_func=lambda: f"ip:{request.remote_addr}")
def password_reset_request():
    data = parse_body(EmailIn)
    auth_service.request_password_reset(data.email)
    return "", 202


@bp.post("/password-reset/confirm")
@doc("Set a new password with the reset token", tags=["Auth"], body=ResetPasswordIn, auth="none")
@limiter.limit("10 per hour", key_func=lambda: f"ip:{request.remote_addr}")
def password_reset_confirm():
    data = parse_body(ResetPasswordIn)
    auth_service.reset_password(data.token, data.new_password)
    return "", 204


@bp.get("/session")
@doc("Who am I (cheap check of the access token)", tags=["Auth"])
@login_required
def session_info():
    return jsonify({"user": user_out(current_user()), "session_id": str(g.current_session.id)})
