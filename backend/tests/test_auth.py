from datetime import UTC, datetime, timedelta

from app.extensions import db
from app.models import AuditEvent, AuthSession
from app.services import email
from tests.conftest import register

CSRF = {"X-Requested-With": "aszda"}


def _token_from_last_email() -> str:
    body = email.outbox[-1].get_content()
    return body.split("token=")[1].split()[0]


def test_register_signs_in_and_sends_verification(client):
    session = register(client)
    assert session.user["email"] == "maya@example.com"
    assert session.user["email_verified"] is False
    assert "aszda_refresh" in client.get_cookie("aszda_refresh", path="/api/auth").key
    assert len(email.outbox) == 1
    assert "verify-email?token=" in email.outbox[0].get_content()


def test_register_rejects_duplicate_email_case_insensitively(client):
    register(client)
    response = client.post("/api/auth/register", json={
        "email": "MAYA@example.com", "password": "Another-Pass-77", "display_name": "M",
        "accept_terms": True})
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "email_taken"


def test_register_rejects_weak_password_and_missing_terms(client):
    weak = client.post("/api/auth/register", json={
        "email": "a@example.com", "password": "short", "display_name": "A", "accept_terms": True})
    assert weak.status_code == 422
    assert weak.get_json()["error"]["code"] == "weak_password"
    no_terms = client.post("/api/auth/register", json={
        "email": "a@example.com", "password": "Correct-Horse-42", "display_name": "A",
        "accept_terms": False})
    assert no_terms.status_code == 422


def test_register_rejects_unknown_fields(client):
    response = client.post("/api/auth/register", json={
        "email": "a@example.com", "password": "Correct-Horse-42", "display_name": "A",
        "accept_terms": True, "role": "admin"})
    assert response.status_code == 422


def test_login_success_and_invalid_credentials(client, app):
    register(client)
    ok = client.post("/api/auth/login", json={"email": "maya@example.com", "password": "Correct-Horse-42"})
    assert ok.status_code == 200
    assert ok.get_json()["token_type"] == "Bearer"

    wrong = client.post("/api/auth/login", json={"email": "maya@example.com", "password": "nope-nope-nope"})
    unknown = client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "nope-nope-nope"})
    assert wrong.status_code == unknown.status_code == 401
    # The same message either way, so emails cannot be enumerated.
    assert wrong.get_json() == unknown.get_json()
    with app.app_context():
        assert db.session.query(AuditEvent).filter_by(action="auth.login_failed").count() == 2


def test_protected_route_requires_valid_token(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401
    session = register(client)
    assert session.get("/api/me").status_code == 200


def test_refresh_rotates_and_detects_reuse(client):
    register(client)
    old_cookie = client.get_cookie("aszda_refresh", path="/api/auth").value

    first = client.post("/api/auth/refresh", headers=CSRF)
    assert first.status_code == 200
    new_cookie = client.get_cookie("aszda_refresh", path="/api/auth").value
    assert new_cookie != old_cookie
    new_access = first.get_json()["access_token"]

    # Replaying the old refresh token is treated as theft: the whole session ends.
    client.set_cookie("aszda_refresh", old_cookie, path="/api/auth")
    replay = client.post("/api/auth/refresh", headers=CSRF)
    assert replay.status_code == 401
    assert client.get("/api/me", headers={"Authorization": f"Bearer {new_access}"}).status_code == 401
    client.set_cookie("aszda_refresh", new_cookie, path="/api/auth")
    assert client.post("/api/auth/refresh", headers=CSRF).status_code == 401


def test_refresh_requires_csrf_header(client):
    register(client)
    response = client.post("/api/auth/refresh")
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "csrf_check_failed"


def test_logout_revokes_session_immediately(client):
    session = register(client)
    assert session.get("/api/me").status_code == 200
    assert client.post("/api/auth/logout", headers=CSRF).status_code == 204
    assert session.get("/api/me").status_code == 401
    assert client.post("/api/auth/refresh", headers=CSRF).status_code == 401


def test_expired_session_is_rejected(client, app):
    session = register(client)
    with app.app_context():
        for s in db.session.query(AuthSession).all():
            s.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.session.commit()
    assert session.get("/api/me").status_code == 401


def test_expired_access_token_is_rejected(client, app):
    session = register(client)
    app.config["ACCESS_TOKEN_TTL"] = timedelta(seconds=-1)
    try:
        expired = client.post("/api/auth/login", json={"email": "maya@example.com",
                                                       "password": "Correct-Horse-42"})
        token = expired.get_json()["access_token"]
    finally:
        app.config["ACCESS_TOKEN_TTL"] = timedelta(minutes=15)
    response = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "token_expired"
    assert session.get("/api/me").status_code == 200


def test_email_verification_flow(client):
    session = register(client)
    token = _token_from_last_email()
    response = client.post("/api/auth/verify-email", json={"token": token})
    assert response.status_code == 200
    assert response.get_json()["user"]["email_verified"] is True
    assert session.get("/api/me").get_json()["user"]["email_verified"] is True
    # Tokens are single-use.
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 400


def test_password_reset_flow_revokes_sessions(client):
    session = register(client)
    assert client.post("/api/auth/password-reset/request", json={"email": "maya@example.com"}).status_code == 202
    # Unknown emails get the same answer and no email.
    sent = len(email.outbox)
    assert client.post("/api/auth/password-reset/request", json={"email": "nobody@example.com"}).status_code == 202
    assert len(email.outbox) == sent

    token = _token_from_last_email()
    assert client.post("/api/auth/password-reset/confirm",
                       json={"token": token, "new_password": "Brand-New-Pass-9"}).status_code == 204
    assert session.get("/api/me").status_code == 401
    assert client.post("/api/auth/login", json={"email": "maya@example.com",
                                                "password": "Correct-Horse-42"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "maya@example.com",
                                                "password": "Brand-New-Pass-9"}).status_code == 200


def test_change_password_keeps_current_session_only(app, client):
    session = register(client)
    other = app.test_client()
    other_session = other.post("/api/auth/login", json={"email": "maya@example.com",
                                                        "password": "Correct-Horse-42"}).get_json()
    response = session.post("/api/me/password", json={"current_password": "Correct-Horse-42",
                                                      "new_password": "Even-Better-Pass-3"})
    assert response.status_code == 204
    assert session.get("/api/me").status_code == 200
    assert other.get("/api/me", headers={"Authorization": f"Bearer {other_session['access_token']}"}).status_code == 401


def test_deactivated_user_cannot_use_token(app, client, make_user):
    session = register(client)
    admin = make_user(admin=True)
    assert admin.patch(f"/api/admin/users/{session.id}", json={"is_active": False}).status_code == 200
    assert session.get("/api/me").status_code == 401


def test_account_deletion_removes_data(client, make_user):
    user = make_user()
    project = user.post("/api/projects", json={"title": "Doomed"}).get_json()["project"]
    bad = user.delete("/api/me", json={"password": "wrong-password", "confirm": "DELETE"})
    assert bad.status_code == 400
    assert user.delete("/api/me", json={"password": "Correct-Horse-42", "confirm": "DELETE"}).status_code == 204
    assert user.get(f"/api/projects/{project['id']}").status_code == 401
