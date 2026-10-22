import io
import uuid

from app.extensions import db
from app.models import CreditAccount, CreditTransaction, GenerationJob
from app.providers.base import ProviderError
from app.services import pricing
from tests.conftest import PNG
from tests.fakes import FakeAsyncVideoAdapter, FakeTextAdapter


def idem() -> dict:
    return {"Idempotency-Key": f"test-{uuid.uuid4()}"}


def text_request(**overrides):
    body = {"provider": "fake-text", "model": "fake-writer", "kind": "text",
            "params": {"prompt": "A fox who sells shoes", "max_output_tokens": 1000}}
    body.update(overrides)
    return body


def balance(app, user) -> int:
    with app.app_context():
        return db.session.query(CreditAccount).filter_by(user_id=user.id).one().balance


def ledger_sum(app, user) -> int:
    with app.app_context():
        account = db.session.query(CreditAccount).filter_by(user_id=user.id).one()
        return sum(t.amount for t in db.session.query(CreditTransaction).filter_by(account_id=account.id))


# Fake text pricing: 1 credit/1000 input tokens, 10 credits/1000 output tokens.
# Estimate: 500 input + 1000 output -> ceil(0.5 + 10) = 11 credits reserved.
# Actual:   100 input + 200 output  -> ceil(0.1 + 2)  = 3 credits charged.


def test_text_job_completes_and_reconciles_credits(app, make_user):
    user = make_user(credits=100)
    pid = user.post("/api/projects", json={"title": "P"}).get_json()["project"]["id"]
    response = user.post("/api/generation-jobs", json=text_request(project_id=pid), headers=idem())
    assert response.status_code == 201, response.get_json()
    job = response.get_json()["job"]
    # The queue runs eagerly in tests, so the job is already finished.
    job = user.get(f"/api/generation-jobs/{job['id']}").get_json()["job"]
    assert job["status"] == "completed"
    assert job["credits_reserved"] == 11
    assert job["credits_charged"] == 3
    assert job["result"]["text"] == "Draft for: A fox who sells shoes"
    assert balance(app, user) == 97
    assert ledger_sum(app, user) == 97  # balance always equals the ledger

    assets = user.get(f"/api/projects/{pid}/assets").get_json()["items"]
    assert len(assets) == 1 and assets[0]["kind"] == "text"
    assert assets[0]["generation_job_id"] == job["id"]


def test_invalid_requests_are_rejected_without_charging(app, make_user):
    user = make_user(credits=100)
    bad_params = user.post("/api/generation-jobs", json=text_request(params={"prompt": ""}), headers=idem())
    assert bad_params.status_code == 422
    extra = user.post("/api/generation-jobs",
                      json=text_request(params={"prompt": "x", "temperature": 2}), headers=idem())
    assert extra.status_code == 422
    unknown_model = user.post("/api/generation-jobs", json=text_request(model="gpt-99"), headers=idem())
    assert unknown_model.status_code == 422
    wrong_kind = user.post("/api/generation-jobs", json=text_request(kind="video"), headers=idem())
    assert wrong_kind.status_code == 422
    unknown_provider = user.post("/api/generation-jobs", json=text_request(provider="nope"), headers=idem())
    assert unknown_provider.status_code == 404
    no_key = user.post("/api/generation-jobs", json=text_request())
    assert no_key.status_code == 400
    assert no_key.get_json()["error"]["code"] == "idempotency_key_required"
    assert balance(app, user) == 100


def test_unconfigured_provider_and_unpriced_model_are_refused(app, make_user):
    user = make_user(credits=100)
    FakeTextAdapter.configured = False
    response = user.post("/api/generation-jobs", json=text_request(), headers=idem())
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "provider_not_configured"
    FakeTextAdapter.configured = True

    pricing.set_override({})
    response = user.post("/api/generation-jobs", json=text_request(), headers=idem())
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "pricing_not_configured"
    assert balance(app, user) == 100


def test_insufficient_credits(app, make_user):
    user = make_user(credits=5)
    response = user.post("/api/generation-jobs", json=text_request(), headers=idem())
    assert response.status_code == 402
    assert response.get_json()["error"]["code"] == "insufficient_credits"
    assert balance(app, user) == 5
    with app.app_context():
        assert db.session.query(GenerationJob).count() == 0


def test_unverified_email_cannot_generate(make_user):
    user = make_user(verified=False, credits=100)
    response = user.post("/api/generation-jobs", json=text_request(), headers=idem())
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "email_not_verified"


def test_duplicate_request_returns_same_job_and_charges_once(app, make_user):
    user = make_user(credits=100)
    headers = idem()
    first = user.post("/api/generation-jobs", json=text_request(), headers=headers)
    second = user.post("/api/generation-jobs", json=text_request(), headers=headers)
    assert first.status_code == 201 and second.status_code == 200
    assert first.get_json()["job"]["id"] == second.get_json()["job"]["id"]
    assert FakeTextAdapter.calls == 1
    assert balance(app, user) == 97
    different = user.post("/api/generation-jobs", json=text_request(params={"prompt": "other"}),
                          headers=headers)
    assert different.status_code == 409
    assert different.get_json()["error"]["code"] == "idempotency_key_reused"


def test_temporary_provider_error_is_retried(app, make_user):
    user = make_user(credits=100)
    FakeTextAdapter.errors = [ProviderError("busy", code="provider_unavailable", retryable=True)]
    job = user.post("/api/generation-jobs", json=text_request(), headers=idem()).get_json()["job"]
    job = user.get(f"/api/generation-jobs/{job['id']}").get_json()["job"]
    assert job["status"] == "completed"
    assert job["attempts"] == 2
    assert FakeTextAdapter.calls == 2
    assert balance(app, user) == 97


def test_permanent_failure_refunds_reservation(app, make_user):
    user = make_user(credits=100)
    FakeTextAdapter.errors = [ProviderError("bad request", code="provider_rejected_request")]
    job = user.post("/api/generation-jobs", json=text_request(), headers=idem()).get_json()["job"]
    job = user.get(f"/api/generation-jobs/{job['id']}").get_json()["job"]
    assert job["status"] == "failed"
    assert job["error"]["code"] == "provider_rejected_request"
    assert job["credits_charged"] == 0
    assert balance(app, user) == 100
    with app.app_context():
        types = sorted(t.tx_type.value for t in db.session.query(CreditTransaction)
                       .filter(CreditTransaction.generation_job_id == job["id"]))
    assert types == ["refund", "reserve"]


def test_retries_give_up_after_max_attempts_and_refund(app, make_user):
    user = make_user(credits=100)
    FakeTextAdapter.errors = [ProviderError("busy", code="provider_unavailable", retryable=True)
                              for _ in range(5)]
    job = user.post("/api/generation-jobs", json=text_request(), headers=idem()).get_json()["job"]
    job = user.get(f"/api/generation-jobs/{job['id']}").get_json()["job"]
    assert job["status"] == "failed"
    assert job["attempts"] == 3
    assert balance(app, user) == 100


def test_refused_request_charges_only_reported_usage(app, make_user):
    user = make_user(credits=100)
    FakeTextAdapter.errors = [ProviderError("declined", code="content_refused",
                                            usage={"input_tokens": 100, "output_tokens": 0})]
    job = user.post("/api/generation-jobs", json=text_request(), headers=idem()).get_json()["job"]
    job = user.get(f"/api/generation-jobs/{job['id']}").get_json()["job"]
    assert job["status"] == "failed"
    assert job["credits_charged"] == 1  # minimum charge for real usage
    assert balance(app, user) == 99
    assert user.post(f"/api/generation-jobs/{job['id']}/retry", headers=idem()).status_code == 409


def test_async_video_job_polls_until_done(app, make_user):
    user = make_user(credits=200)
    pid = user.post("/api/projects", json={"title": "P"}).get_json()["project"]["id"]
    ref = user.post(f"/api/projects/{pid}/assets", data={"file": (io.BytesIO(PNG), "ref.png")},
                    content_type="multipart/form-data").get_json()["asset"]
    response = user.post("/api/generation-jobs", headers=idem(), json={
        "provider": "fake-video", "model": "fake-motion", "kind": "video", "project_id": pid,
        "params": {"prompt_text": "A fox runs", "duration": 5, "reference_asset_id": ref["id"]}})
    assert response.status_code == 201, response.get_json()
    job = user.get(f"/api/generation-jobs/{response.get_json()['job']['id']}").get_json()["job"]
    assert job["status"] == "completed"
    assert FakeAsyncVideoAdapter.poll_calls == 2
    assert job["credits_charged"] == 50  # 5 seconds * 10 credits
    video = user.get(f"/api/projects/{pid}/assets?kind=video").get_json()["items"]
    assert len(video) == 1 and video[0]["duration_seconds"] == 5
    assert balance(app, user) == 150


def test_async_provider_failure_refunds(app, make_user):
    user = make_user(credits=200)
    FakeAsyncVideoAdapter.final = "fail"
    response = user.post("/api/generation-jobs", headers=idem(), json={
        "provider": "fake-video", "model": "fake-motion", "kind": "video",
        "params": {"prompt_text": "A fox runs", "duration": 5}})
    job = user.get(f"/api/generation-jobs/{response.get_json()['job']['id']}").get_json()["job"]
    assert job["status"] == "failed" and job["error"]["code"] == "fake_failed"
    assert balance(app, user) == 200


def test_cancel_running_async_job_refunds_and_cancels_at_provider(app, make_user):
    user = make_user(credits=200)
    FakeAsyncVideoAdapter.stay_pending = True
    app.config["PROVIDER_MAX_POLL_MINUTES"] = 60
    # Stop the eager poll loop from spinning forever: allow only a few polls.
    from app.services import generation_service

    original = generation_service._enqueue_poll
    generation_service._enqueue_poll = lambda job: None
    try:
        response = user.post("/api/generation-jobs", headers=idem(), json={
            "provider": "fake-video", "model": "fake-motion", "kind": "video",
            "params": {"prompt_text": "A fox runs", "duration": 5}})
        job = response.get_json()["job"]
        assert user.get(f"/api/generation-jobs/{job['id']}").get_json()["job"]["status"] == "processing"
        assert balance(app, user) == 150
        cancelled = user.post(f"/api/generation-jobs/{job['id']}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.get_json()["job"]["status"] == "cancelled"
        assert FakeAsyncVideoAdapter.cancelled == [f"task-{job['id']}"]
        assert balance(app, user) == 200
        # Cancelling twice is refused and does not refund twice.
        assert user.post(f"/api/generation-jobs/{job['id']}/cancel").status_code == 409
        assert balance(app, user) == 200
        assert ledger_sum(app, user) == 200
        # A late poll arriving after cancellation changes nothing.
        with app.app_context():
            generation_service.poll_job(uuid.UUID(job["id"]))
        assert user.get(f"/api/generation-jobs/{job['id']}").get_json()["job"]["status"] == "cancelled"
        assert balance(app, user) == 200
    finally:
        generation_service._enqueue_poll = original


def test_retry_failed_job_creates_new_linked_job(app, make_user):
    user = make_user(credits=100)
    FakeTextAdapter.errors = [ProviderError("bad", code="provider_rejected_request")]
    failed = user.post("/api/generation-jobs", json=text_request(), headers=idem()).get_json()["job"]
    headers = idem()
    retried = user.post(f"/api/generation-jobs/{failed['id']}/retry", headers=headers)
    assert retried.status_code == 201
    new_job = retried.get_json()["job"]
    assert new_job["retry_of_id"] == failed["id"]
    assert user.get(f"/api/generation-jobs/{new_job['id']}").get_json()["job"]["status"] == "completed"
    again = user.post(f"/api/generation-jobs/{failed['id']}/retry", headers=headers)
    assert again.status_code == 200 and again.get_json()["job"]["id"] == new_job["id"]
    completed_retry = user.post(f"/api/generation-jobs/{new_job['id']}/retry", headers=idem())
    assert completed_retry.status_code == 409
    assert balance(app, user) == 97


def test_usage_limits(app, make_user):
    user = make_user(credits=1000)
    app.config["MAX_CREDITS_PER_JOB"] = 10
    try:
        too_big = user.post("/api/generation-jobs", json=text_request(), headers=idem())
        assert too_big.status_code == 422 and too_big.get_json()["error"]["code"] == "job_too_expensive"
    finally:
        app.config["MAX_CREDITS_PER_JOB"] = 500
    app.config["DAILY_JOB_LIMIT"] = 2
    try:
        for _ in range(2):
            assert user.post("/api/generation-jobs", json=text_request(), headers=idem()).status_code == 201
        third = user.post("/api/generation-jobs", json=text_request(), headers=idem())
        assert third.status_code == 429 and third.get_json()["error"]["code"] == "daily_limit_reached"
    finally:
        app.config["DAILY_JOB_LIMIT"] = 50
    app.config["MONTHLY_CREDIT_LIMIT"] = 10
    try:
        over = user.post("/api/generation-jobs", json=text_request(), headers=idem())
        assert over.status_code == 429 and over.get_json()["error"]["code"] == "monthly_limit_reached"
    finally:
        app.config["MONTHLY_CREDIT_LIMIT"] = 5000


def test_active_job_limit(app, make_user):
    user = make_user(credits=1000)
    FakeAsyncVideoAdapter.stay_pending = True
    from app.services import generation_service

    original = generation_service._enqueue_poll
    generation_service._enqueue_poll = lambda job: None
    app.config["MAX_ACTIVE_JOBS_PER_USER"] = 1
    try:
        body = {"provider": "fake-video", "model": "fake-motion", "kind": "video",
                "params": {"prompt_text": "x", "duration": 2}}
        assert user.post("/api/generation-jobs", json=body, headers=idem()).status_code == 201
        second = user.post("/api/generation-jobs", json=body, headers=idem())
        assert second.status_code == 429
        assert second.get_json()["error"]["code"] == "too_many_active_jobs"
    finally:
        generation_service._enqueue_poll = original
        app.config["MAX_ACTIVE_JOBS_PER_USER"] = 3


def test_cross_user_job_access_is_blocked(make_user):
    owner, intruder = make_user(credits=100), make_user(credits=100)
    job = owner.post("/api/generation-jobs", json=text_request(), headers=idem()).get_json()["job"]
    assert intruder.get(f"/api/generation-jobs/{job['id']}").status_code == 404
    assert intruder.post(f"/api/generation-jobs/{job['id']}/cancel").status_code == 404
    assert intruder.post(f"/api/generation-jobs/{job['id']}/retry", headers=idem()).status_code == 404
    assert intruder.get("/api/generation-jobs").get_json()["total"] == 0
    other_pid = owner.post("/api/projects", json={"title": "Owner's"}).get_json()["project"]["id"]
    sneaky = intruder.post("/api/generation-jobs", json=text_request(project_id=other_pid), headers=idem())
    assert sneaky.status_code == 404


def test_cannot_use_someone_elses_asset_as_reference(make_user):
    owner, intruder = make_user(credits=100), make_user(credits=200)
    pid = owner.post("/api/projects", json={"title": "P"}).get_json()["project"]["id"]
    ref = owner.post(f"/api/projects/{pid}/assets", data={"file": (io.BytesIO(PNG), "r.png")},
                     content_type="multipart/form-data").get_json()["asset"]
    response = intruder.post("/api/generation-jobs", headers=idem(), json={
        "provider": "fake-video", "model": "fake-motion", "kind": "video",
        "params": {"prompt_text": "x", "duration": 2, "reference_asset_id": ref["id"]}})
    assert response.status_code == 404


def test_quote_and_provider_catalog(make_user):
    user = make_user(credits=40)
    quote = user.post("/api/generation-jobs/quote", json={
        "provider": "fake-text", "model": "fake-writer", "kind": "text",
        "params": {"prompt": "x", "max_output_tokens": 1000}}).get_json()
    assert quote == {"priced": True, "estimated_credits": 11, "balance": 40,
                     "estimated_usage": {"input_tokens": 500, "output_tokens": 1000},
                     "provider": "fake-text", "model": "fake-writer", "fallback_used": False}
    providers = {p["name"]: p for p in user.get("/api/providers").get_json()["providers"]}
    assert providers["fake-text"]["models"][0]["available"] is True
    # Real adapters have no API key in tests, so they must be reported unavailable.
    for name in ("anthropic", "openai", "runway"):
        assert providers[name]["configured"] is False
        assert all(not m["available"] for m in providers[name]["models"])
    body = str(providers)
    assert "sk-" not in body and "api_key" not in body.lower()
