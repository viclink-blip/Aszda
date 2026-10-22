"""Test fixtures.

Tests run against a real PostgreSQL database (TEST_DATABASE_URL, default
postgresql+psycopg://aszda:aszda@localhost:5432/aszda_test) because row locks,
JSONB and constraints are part of what is being tested. The schema is created
by running the real Alembic migrations once per test session.

No external AI service is ever called: providers are replaced by fakes.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from app import create_app
from app.extensions import db
from app.models import Role, User
from app.providers import registry
from app.services import email, pricing
from tests.fakes import FakeAsyncVideoAdapter, FakeTextAdapter

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200

TABLES = ["provider_costs", "signup_grant_claims", "generation_prices", "billing_item_settings", "payment_events", "payments", "subscriptions",
          "scene_characters", "credit_transactions", "credit_accounts", "assets", "generation_jobs",
          "characters", "scenes", "projects", "refresh_tokens", "auth_sessions", "user_tokens",
          "user_profiles", "audit_events", "users"]


@pytest.fixture(scope="session")
def app():
    storage_root = tempfile.mkdtemp(prefix="aszda-test-storage-")
    os.environ.setdefault("ASZDA_ENV", "testing")
    application = create_app("testing")
    application.config["LOCAL_STORAGE_ROOT"] = storage_root
    with application.app_context():
        from flask_migrate import downgrade, upgrade

        migrations = os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations")
        downgrade(directory=migrations, revision="base")
        upgrade(directory=migrations)
    yield application
    shutil.rmtree(storage_root, ignore_errors=True)


@pytest.fixture(autouse=True)
def clean_state(app):
    with app.app_context():
        db.session.execute(text(f"TRUNCATE {', '.join(TABLES)} CASCADE"))
        db.session.commit()
    email.outbox.clear()
    registry.reset()
    registry.register(FakeTextAdapter())
    registry.register(FakeAsyncVideoAdapter())
    FakeTextAdapter.reset()
    FakeAsyncVideoAdapter.reset()
    pricing.set_override({
        "fake-text:fake-writer": pricing.ModelPrice(
            credits_per_1000={"input_tokens": 1, "output_tokens": 10}, minimum_credits=1),
        "fake-video:fake-motion": pricing.ModelPrice(
            credits_per_1000={"video_seconds": 10_000}, minimum_credits=5),
    })
    yield
    pricing.set_override(None)


@pytest.fixture()
def client(app):
    return app.test_client()


class Session:
    """A signed-in test user."""

    def __init__(self, client, data: dict):
        self.client = client
        self.token = data["access_token"]
        self.user = data["user"]
        self.id = uuid.UUID(self.user["id"])

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def get(self, url, **kw):
        return self.client.get(url, headers={**self.headers, **kw.pop("headers", {})}, **kw)

    def post(self, url, **kw):
        return self.client.post(url, headers={**self.headers, **kw.pop("headers", {})}, **kw)

    def patch(self, url, **kw):
        return self.client.patch(url, headers={**self.headers, **kw.pop("headers", {})}, **kw)

    def put(self, url, **kw):
        return self.client.put(url, headers={**self.headers, **kw.pop("headers", {})}, **kw)

    def delete(self, url, **kw):
        return self.client.delete(url, headers={**self.headers, **kw.pop("headers", {})}, **kw)


def register(client, email_addr: str = "maya@example.com", password: str = "Correct-Horse-42",
             name: str = "Maya") -> Session:
    response = client.post("/api/auth/register", json={
        "email": email_addr, "password": password, "display_name": name, "accept_terms": True})
    assert response.status_code == 201, response.get_json()
    return Session(client, response.get_json())


@pytest.fixture()
def make_user(app):
    """Factory: make_user(email, verified=True, admin=False, credits=0) -> Session."""

    def factory(email_addr: str | None = None, *, verified: bool = True, admin: bool = False,
                credits: int = 0) -> Session:
        email_addr = email_addr or f"user-{uuid.uuid4().hex[:8]}@example.com"
        client = app.test_client()
        session = register(client, email_addr)
        with app.app_context():
            user = db.session.get(User, session.id)
            if verified:
                user.email_verified_at = datetime.now(UTC)
            if admin:
                user.role = Role.ADMIN
            if credits:
                from app.services import credit_service

                credit_service.grant(user.id, credits, reference=f"test:{uuid.uuid4()}",
                                     reason="test", actor_id=None)
            db.session.commit()
        if admin:
            # Sign in again so the access token carries the admin role.
            response = client.post("/api/auth/login", json={"email": email_addr,
                                                            "password": "Correct-Horse-42"})
            session = Session(client, response.get_json())
        return session

    return factory
