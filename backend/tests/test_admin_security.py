from app import create_app
from app.extensions import db
from app.models import AuditEvent

ADMIN_ENDPOINTS = ["/api/admin/overview", "/api/admin/users", "/api/admin/jobs", "/api/admin/usage",
                   "/api/admin/providers", "/api/admin/audit-events", "/api/admin/credit-transactions"]


def test_admin_endpoints_require_admin(client, make_user):
    user = make_user()
    for url in ADMIN_ENDPOINTS:
        assert client.get(url).status_code == 401, url
        assert user.get(url).status_code == 403, url
    assert user.post(f"/api/admin/users/{user.id}/credits", json={"amount": 999, "reason": "free"}).status_code == 403
    assert user.patch(f"/api/admin/users/{user.id}", json={"role": "admin"}).status_code == 403


def test_admin_can_list_users_and_grant_credits_with_audit(app, make_user):
    admin, user = make_user(admin=True), make_user("pat@example.com")
    for url in ADMIN_ENDPOINTS:
        assert admin.get(url).status_code == 200, url
    found = admin.get("/api/admin/users?q=pat").get_json()
    assert found["total"] == 1 and found["items"][0]["credit_balance"] == 0

    granted = admin.post(f"/api/admin/users/{user.id}/credits", json={"amount": 250, "reason": "Beta tester"})
    assert granted.status_code == 201
    assert user.get("/api/me/credits").get_json()["account"]["balance"] == 250
    removed = admin.post(f"/api/admin/users/{user.id}/credits", json={"amount": -50, "reason": "Correction"})
    assert removed.status_code == 201
    too_much = admin.post(f"/api/admin/users/{user.id}/credits", json={"amount": -1000, "reason": "Oops"})
    assert too_much.status_code == 402
    assert user.get("/api/me/credits").get_json()["account"]["balance"] == 200

    with app.app_context():
        events = db.session.query(AuditEvent).filter_by(action="admin.credits_adjusted").all()
        assert len(events) == 2
        assert all(e.actor_user_id == admin.id for e in events)


def test_admin_cannot_lock_themselves_out(make_user):
    admin = make_user(admin=True)
    response = admin.patch(f"/api/admin/users/{admin.id}", json={"is_active": False})
    assert response.status_code == 422


def test_role_change_takes_effect_and_revokes_sessions(make_user):
    admin, user = make_user(admin=True), make_user()
    assert admin.patch(f"/api/admin/users/{user.id}", json={"role": "admin"}).status_code == 200
    assert user.get("/api/me").status_code == 401  # must sign in again to get the new role


def test_admin_provider_view_never_exposes_keys(app, make_user):
    admin = make_user(admin=True)
    app.config["ANTHROPIC_API_KEY"] = "sk-ant-secret-value-123"
    try:
        body = admin.get("/api/admin/providers").get_data(as_text=True)
    finally:
        app.config["ANTHROPIC_API_KEY"] = ""
    assert "sk-ant-secret-value-123" not in body
    assert "ANTHROPIC_API_KEY" in body  # the variable name is shown, never the value


def test_security_headers_present(client):
    response = client.get("/api/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]


def test_errors_do_not_leak_internals(client, make_user):
    user = make_user()
    response = user.get("/api/projects/not-a-uuid")
    assert response.status_code == 404
    assert "Traceback" not in response.get_data(as_text=True)


def test_login_rate_limit():
    app = create_app("testing")
    app.config["RATELIMIT_ENABLED"] = True
    from app.extensions import limiter

    limiter.init_app(app)
    client = app.test_client()
    codes = [client.post("/api/auth/login", json={"email": "x@example.com", "password": "wrong-pass"}).status_code
             for _ in range(12)]
    assert codes[:10] == [401] * 10
    assert codes[10] == 429
    limiter.enabled = False


def test_openapi_document(client):
    spec = client.get("/api/openapi.json").get_json()
    assert spec["openapi"] == "3.1.0"
    assert "/api/generation-jobs" in spec["paths"]
    assert "post" in spec["paths"]["/api/projects/{project_id}/scenes"]
    assert "RegisterIn" in spec["components"]["schemas"]


def test_health(client):
    assert client.get("/api/health").get_json()["status"] == "ok"
    ready = client.get("/api/health/ready")
    assert ready.status_code == 200
    assert ready.get_json()["checks"]["database"] == "ok"
