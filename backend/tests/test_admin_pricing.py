"""Admin-configurable credit costs and allowances, per-plan monthly limits and stuck-job recovery."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from app.billing import catalog as catalog_mod
from app.extensions import db
from app.models import (
    AuditEvent,
    CreditAccount,
    GenerationJob,
    JobStatus,
    Subscription,
    SubscriptionStatus,
)
from app.services import generation_service, pricing
from tests.fakes import FakeAsyncVideoAdapter

TEXT_PRICE = {"credits_per_1000": {"input_tokens": 1, "output_tokens": 10}, "minimum_credits": 1,
              "provider_usd_per_1000": {"input_tokens": 0.004, "output_tokens": 0.02},
              "provider_price_source": "test"}


@pytest.fixture()
def admin_prices(app):
    """Use the database (admin) prices instead of the test override."""
    pricing.set_override(None)
    yield
    pricing.set_override(None)


def idem():
    return {"Idempotency-Key": f"k-{uuid.uuid4()}"}


def text_job(user):
    return user.post("/api/generation-jobs", headers=idem(), json={
        "provider": "fake-text", "model": "fake-writer", "kind": "text",
        "params": {"prompt": "x", "max_output_tokens": 1000}})


def balance(app, user):
    with app.app_context():
        return db.session.query(CreditAccount).filter_by(user_id=user.id).one().balance


# ---- Generation prices -----------------------------------------------------------------

def test_only_admins_can_change_pricing(make_user, admin_prices):
    user = make_user()
    assert user.get("/api/admin/pricing").status_code == 403
    assert user.put("/api/admin/pricing/generation/fake-text/fake-writer", json=TEXT_PRICE).status_code == 403
    assert user.put("/api/admin/pricing/billing/credit_package/small", json={"credits": 9}).status_code == 403


def test_admin_price_is_used_and_audited(app, make_user, admin_prices):
    admin, user = make_user(admin=True), make_user(credits=100)
    assert text_job(user).status_code == 409  # nothing priced yet
    response = admin.put("/api/admin/pricing/generation/fake-text/fake-writer", json=TEXT_PRICE)
    assert response.status_code == 200, response.get_json()
    row = next(r for r in response.get_json()["generation"] if r["model"] == "fake-writer")
    assert row["source"] == "admin"
    assert row["reference_jobs"][0]["credits"] == 42      # 1.5 + 40 -> 42 credits
    assert row["reference_jobs"][0]["provider_usd"] == 0.086
    job = text_job(user)
    assert job.status_code == 201
    assert job.get_json()["job"]["credits_reserved"] == 11
    with app.app_context():
        event = db.session.query(AuditEvent).filter_by(action="admin.generation_price_set").one()
        assert event.actor_user_id == admin.id
        assert event.details["after"]["credits_per_1000"] == {"input_tokens": 1, "output_tokens": 10}


def test_disabling_a_model_stops_new_jobs(make_user, admin_prices):
    admin, user = make_user(admin=True), make_user(credits=100)
    admin.put("/api/admin/pricing/generation/fake-text/fake-writer", json={**TEXT_PRICE, "enabled": False})
    response = text_job(user)
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "pricing_not_configured"


def test_generation_price_validation(make_user, admin_prices):
    admin = make_user(admin=True)
    url = "/api/admin/pricing/generation/fake-text/fake-writer"
    assert admin.put(url, json={**TEXT_PRICE, "credits_per_1000": {"output_tokens": 10}}).status_code == 422
    assert admin.put(url, json={**TEXT_PRICE, "credits_per_1000": {"input_tokens": 1, "output_tokens": 1,
                                                                   "pixels": 1}}).status_code == 422
    assert admin.put(url, json={**TEXT_PRICE, "credits_per_1000": {"input_tokens": -1,
                                                                   "output_tokens": 1}}).status_code == 422
    assert admin.put(url, json={**TEXT_PRICE, "minimum_credits": 0}).status_code == 422
    assert admin.put("/api/admin/pricing/generation/fake-text/nope", json=TEXT_PRICE).status_code == 404


def test_price_change_does_not_affect_a_running_job(app, make_user, admin_prices):
    admin, user = make_user(admin=True), make_user(credits=500)
    admin.put("/api/admin/pricing/generation/fake-video/fake-motion",
              json={"credits_per_1000": {"video_seconds": 10_000}, "minimum_credits": 5})
    FakeAsyncVideoAdapter.stay_pending = True
    original = generation_service._enqueue_poll
    generation_service._enqueue_poll = lambda job: None
    try:
        job = user.post("/api/generation-jobs", headers=idem(), json={
            "provider": "fake-video", "model": "fake-motion", "kind": "video",
            "params": {"prompt_text": "x", "duration": 5}}).get_json()["job"]
        assert job["credits_reserved"] == 50
        # The admin triples the price while the video is rendering.
        admin.put("/api/admin/pricing/generation/fake-video/fake-motion",
                  json={"credits_per_1000": {"video_seconds": 30_000}, "minimum_credits": 5})
        FakeAsyncVideoAdapter.stay_pending = False
        FakeAsyncVideoAdapter.polls_until_done = 0
        with app.app_context():
            generation_service.poll_job(uuid.UUID(job["id"]))
    finally:
        generation_service._enqueue_poll = original
    done = user.get(f"/api/generation-jobs/{job['id']}").get_json()["job"]
    assert done["status"] == "completed" and done["credits_charged"] == 50  # the price at submission
    assert balance(app, user) == 450


# ---- Plan allowances and package credits -----------------------------------------------

def test_admin_sets_package_and_plan_credits(make_user, admin_prices):
    catalog_mod.set_override(None)
    admin = make_user(admin=True)
    small = admin.put("/api/admin/pricing/billing/credit_package/small", json={"credits": 520})
    assert small.status_code == 200
    starter = admin.put("/api/admin/pricing/billing/plan/starter",
                        json={"credits": 1000, "paystack_plan_code": "PLN_abc123", "monthly_credit_limit": 3000})
    assert starter.status_code == 200
    public = admin.client.get("/api/billing/catalog").get_json()
    assert next(p for p in public["credit_packages"] if p["code"] == "small")["credits"] == 520
    plan = next(p for p in public["plans"] if p["code"] == "starter")
    assert plan["monthly_credits"] == 1000 and plan["purchasable"] is True
    assert plan["price"]["formatted"] == "$9"  # the USD price is untouched


def test_billing_item_validation(make_user, admin_prices):
    catalog_mod.set_override(None)
    admin = make_user(admin=True)
    assert admin.put("/api/admin/pricing/billing/plan/free", json={"credits": 100}).status_code == 422
    assert admin.put("/api/admin/pricing/billing/plan/unknown", json={"credits": 100}).status_code == 404
    assert admin.put("/api/admin/pricing/billing/plan/starter",
                     json={"credits": 1000, "monthly_credit_limit": 500}).status_code == 422
    assert admin.put("/api/admin/pricing/billing/plan/starter",
                     json={"paystack_plan_code": "nope"}).status_code == 422
    assert admin.put("/api/admin/pricing/billing/credit_package/small",
                     json={"credits": 0}).status_code == 422
    assert admin.put("/api/admin/pricing/billing/credit_package/small",
                     json={"credits": 5, "price_usd_cents": 1}).status_code == 422


def test_margin_analysis(make_user, admin_prices):
    catalog_mod.set_override(None)
    admin = make_user(admin=True)
    admin.put("/api/admin/pricing/generation/fake-text/fake-writer", json=TEXT_PRICE)
    data = admin.put("/api/admin/pricing/billing/credit_package/small", json={"credits": 500}).get_json()
    small = next(p for p in data["credit_packages"] if p["code"] == "small")
    worst = data["assumptions"]["worst_case_provider_usd_per_credit"]
    assert worst is not None and worst > 0
    assert small["usd_per_credit"] == 0.01
    assert small["net_revenue_usd"] == pytest.approx(5 * (1 - 0.038))
    assert small["max_provider_cost_usd"] == pytest.approx(500 * worst, rel=1e-3)
    assert small["gross_margin_percent"] == pytest.approx(
        (small["net_revenue_usd"] - small["max_provider_cost_usd"]) / small["net_revenue_usd"] * 100, abs=0.1)


# ---- Per-plan monthly limit ----------------------------------------------------------------

def test_plan_monthly_limit_replaces_global_limit(app, make_user):
    catalog_mod.set_override(None)
    admin, user = make_user(admin=True), make_user(credits=1000)
    app.config["MONTHLY_CREDIT_LIMIT"] = 13  # first job reserves 11 and is charged 3; 3 + 11 > 13
    try:
        assert text_job(user).status_code == 201
        assert text_job(user).status_code == 429
        admin.put("/api/admin/pricing/billing/plan/studio_max", json={"credits": 100, "monthly_credit_limit": 200})
        with app.app_context():
            db.session.add(Subscription(user_id=user.id, plan_code="studio_max", status=SubscriptionStatus.ACTIVE))
            db.session.commit()
        assert text_job(user).status_code == 201  # the plan's own limit (200) applies now
    finally:
        app.config["MONTHLY_CREDIT_LIMIT"] = 5000


# ---- Stuck-job recovery ----------------------------------------------------------------------

def _age(app, job_id, minutes, **values):
    with app.app_context():
        db.session.execute(update(GenerationJob).where(GenerationJob.id == job_id).values(
            updated_at=datetime.now(UTC) - timedelta(minutes=minutes), **values))
        db.session.commit()


def test_lost_queue_message_is_refunded_once(app, make_user):
    user = make_user(credits=100)
    original = generation_service._enqueue_run
    generation_service._enqueue_run = lambda job, countdown=0: None  # the queue "loses" the task
    try:
        job = text_job(user).get_json()["job"]
    finally:
        generation_service._enqueue_run = original
    assert balance(app, user) == 89
    with app.app_context():
        assert generation_service.reap_stuck_jobs()["failed_queued"] == 0  # too recent to touch
    _age(app, job["id"], 31)
    with app.app_context():
        assert generation_service.reap_stuck_jobs()["failed_queued"] == 1
        assert generation_service.reap_stuck_jobs()["failed_queued"] == 0  # second run: nothing to do
    final = user.get(f"/api/generation-jobs/{job['id']}").get_json()["job"]
    assert final["status"] == "failed" and final["error"]["code"] == "queue_timeout"
    assert balance(app, user) == 100


def test_lost_worker_is_refunded(app, make_user):
    user = make_user(credits=100)
    original = generation_service._enqueue_run
    generation_service._enqueue_run = lambda job, countdown=0: None
    try:
        job = text_job(user).get_json()["job"]
    finally:
        generation_service._enqueue_run = original
    _age(app, job["id"], 46, status=JobStatus.PROCESSING)  # the worker died mid-call
    with app.app_context():
        assert generation_service.reap_stuck_jobs()["failed_lost_worker"] == 1
    assert user.get(f"/api/generation-jobs/{job['id']}").get_json()["job"]["error"]["code"] == "worker_lost"
    assert balance(app, user) == 100


def test_lost_poll_is_resumed_and_times_out_with_refund(app, make_user):
    user = make_user(credits=200)
    FakeAsyncVideoAdapter.stay_pending = True
    original = generation_service._enqueue_poll
    generation_service._enqueue_poll = lambda job: None  # the poll message is lost
    try:
        job = user.post("/api/generation-jobs", headers=idem(), json={
            "provider": "fake-video", "model": "fake-motion", "kind": "video",
            "params": {"prompt_text": "x", "duration": 5}}).get_json()["job"]
        _age(app, job["id"], 120, submitted_at=datetime.now(UTC) - timedelta(minutes=120))
        with app.app_context():
            assert generation_service.reap_stuck_jobs()["repolled"] == 1
    finally:
        generation_service._enqueue_poll = original
    final = user.get(f"/api/generation-jobs/{job['id']}").get_json()["job"]
    assert final["status"] == "failed" and final["error"]["code"] == "provider_timeout"
    assert FakeAsyncVideoAdapter.cancelled  # cancelled at the provider too
    assert balance(app, user) == 200


# ---- The proposed pricing document --------------------------------------------------------

def _proposal():
    import json
    from pathlib import Path

    return json.loads((Path(__file__).parent.parent / "pricing.approved.json").read_text())


def test_pricing_dry_run_changes_nothing(app, admin_prices):
    from app.models import BillingItemSetting, GenerationPrice
    from app.services.pricing_settings import apply_pricing_document

    catalog_mod.set_override(None)
    with app.app_context():
        lines = apply_pricing_document(_proposal(), actor_id=None, commit=False)
        assert len(lines) == 14
        assert db.session.query(GenerationPrice).count() == 0
        assert db.session.query(BillingItemSetting).count() == 0


def test_proposal_keeps_at_least_50_percent_margin(app, make_user, admin_prices):
    from app.services.pricing_settings import apply_pricing_document

    catalog_mod.set_override(None)
    with app.app_context():
        apply_pricing_document(_proposal(), actor_id=None, commit=True)
    data = make_user(admin=True).get("/api/admin/pricing").get_json()
    rows = {(r["provider"], r["model"]): r for r in data["generation"]}
    jobs = {(p, m, j["name"]): j["credits"] for (p, m), r in rows.items() for j in r["reference_jobs"]}
    assert jobs[("runway", "gen4.5", "5-second clip")] == 160
    assert jobs[("runway", "gen4.5", "10-second clip (longest)")] == 320
    assert jobs[("runway", "veo3.1_fast", "8-second clip, no audio")] == 216
    assert jobs[("runway", "veo3.1_fast", "8-second clip with audio")] == 320
    assert jobs[("anthropic", "claude-opus-5-5", "Script draft: 1,500 tokens in, 4,000 out")] == 23
    assert jobs[("openai", "tts-1", "1,000 characters (about 1 minute of speech)")] == 4
    # Every plan and package keeps >= 50% gross margin even if all credits go to the
    # most expensive generation per credit, after the 3.8% card fee.
    for item in data["plans"] + data["credit_packages"]:
        if item["price"]["amount_minor"]:
            assert item["gross_margin_percent"] >= 50, item
    # The largest single job fits the per-job safety cap.
    assert max(c for c in jobs.values() if c) <= app.config["MAX_CREDITS_PER_JOB"]
    print("\nMARGINS", {i["name"]: (i["credits"], i["usd_per_credit"], i["max_provider_cost_usd"],
                                    i["gross_margin_percent"]) for i in data["plans"] + data["credit_packages"]},
          "WORST", data["assumptions"]["worst_case_provider_usd_per_credit"])
