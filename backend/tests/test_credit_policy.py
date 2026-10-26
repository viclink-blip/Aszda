"""Credit policy: plan credits expire at the end of their billing period (no rollover),
purchased credits never expire, plan credits are spent first, the free sign-up grant is
given once per inbox, and provider safety blocks are refunded and recorded as ASZDA's cost."""

import threading
import uuid
from datetime import UTC, datetime, timedelta

from app.extensions import db
from app.models import CreditAccount, CreditTransaction, GenerationJob, ProviderCost, SignupGrantClaim
from app.providers.base import ProviderError
from app.services import credit_service, generation_service
from app.services.auth_service import canonical_email
from app.services.email import outbox
from tests import test_billing
from tests.conftest import register
from tests.fakes import FakeAsyncVideoAdapter
from tests.test_billing import checkout

fake_paystack = test_billing.fake_paystack  # shared fixture


def idem() -> dict:
    return {"Idempotency-Key": f"test-{uuid.uuid4()}"}


def text_request():
    return {"provider": "fake-text", "model": "fake-writer", "kind": "text",
            "params": {"prompt": "A fox who sells shoes", "max_output_tokens": 1000}}


def video_request(duration=5):
    return {"provider": "fake-video", "model": "fake-motion", "kind": "video",
            "params": {"prompt_text": "A fox runs", "duration": duration}}


def give_plan(app, user, credits, *, expires_in=timedelta(days=30), ref=None):
    with app.app_context():
        credit_service.start_plan_period(user.id, credits, expires_at=datetime.now(UTC) + expires_in,
                                         reference=ref or f"test-plan:{uuid.uuid4()}", reason="test plan")
        db.session.commit()


def give_purchased(app, user, credits):
    with app.app_context():
        credit_service.add_purchased(user.id, credits, reference=f"test-buy:{uuid.uuid4()}", reason="test")
        db.session.commit()


def parts(app, user) -> tuple[int, int, int]:
    """(plan, purchased, total) as the user would see them; checks every invariant on the way."""
    with app.app_context():
        credit_service.get_account(user.id)  # applies a due expiry, like any read
        db.session.commit()
        account = db.session.query(CreditAccount).filter_by(user_id=user.id).one()
        txs = db.session.query(CreditTransaction).filter_by(account_id=account.id).all()
        assert account.balance == account.plan_balance + account.purchased_balance
        assert account.plan_balance == sum(t.plan_amount for t in txs)
        assert account.purchased_balance == sum(t.purchased_amount for t in txs)
        assert all(t.amount == t.plan_amount + t.purchased_amount for t in txs)
        return account.plan_balance, account.purchased_balance, account.balance


def tx_types(app, user) -> list[str]:
    with app.app_context():
        account = db.session.query(CreditAccount).filter_by(user_id=user.id).one()
        return [t.tx_type.value for t in db.session.query(CreditTransaction).filter_by(account_id=account.id)
                .order_by(CreditTransaction.created_at)]


def expire_now(app, user):
    """Move the end of the user's billing period into the past."""
    with app.app_context():
        account = db.session.query(CreditAccount).filter_by(user_id=user.id).one()
        account.plan_credits_expire_at = datetime.now(UTC) - timedelta(seconds=1)
        db.session.commit()


# ---- Spending order and expiry ----------------------------------------------------------------

def test_plan_credits_are_spent_first_and_unused_returns_where_it_came_from(app, make_user):
    user = make_user()
    give_plan(app, user, 8)
    give_purchased(app, user, 20)
    # Text job: 11 reserved (8 plan + 3 purchased), 3 charged (from plan), 8 returned.
    job = user.post("/api/generation-jobs", json=text_request(), headers=idem()).get_json()["job"]
    assert user.get(f"/api/generation-jobs/{job['id']}").get_json()["job"]["credits_charged"] == 3
    assert parts(app, user) == (5, 20, 25)
    with app.app_context():
        reserve = db.session.query(CreditTransaction).filter_by(reference=f"job:{job['id']}:reserve").one()
        release = db.session.query(CreditTransaction).filter_by(reference=f"job:{job['id']}:release").one()
        assert (reserve.plan_amount, reserve.purchased_amount) == (-8, -3)
        assert (release.plan_amount, release.purchased_amount) == (5, 3)


def test_plan_credits_expire_at_period_end_and_purchased_credits_stay(app, make_user):
    user = make_user()
    give_plan(app, user, 300)
    give_purchased(app, user, 200)
    assert parts(app, user) == (300, 200, 500)
    expire_now(app, user)
    # Reading the balance already reflects the expiry (no scheduler needed)...
    account = user.get("/api/me/credits").get_json()["account"]
    assert account == {**account, "balance": 200, "plan_balance": 0, "purchased_balance": 200,
                       "plan_credits_expire_at": None}
    assert parts(app, user) == (0, 200, 200)
    assert tx_types(app, user)[-1] == "expire"
    # ...and running the scheduled sweep afterwards changes nothing more.
    with app.app_context():
        assert credit_service.expire_due_plan_credits() == 0
    assert tx_types(app, user).count("expire") == 1


def test_scheduled_sweep_expires_plan_credits(app, make_user):
    user = make_user()
    give_plan(app, user, 100)
    expire_now(app, user)
    with app.app_context():
        assert credit_service.expire_due_plan_credits() == 1
        assert credit_service.expire_due_plan_credits() == 0
    assert parts(app, user) == (0, 0, 0)


def test_expired_plan_credits_cannot_be_spent(app, make_user):
    user = make_user()
    give_plan(app, user, 100)
    expire_now(app, user)
    response = user.post("/api/generation-jobs", json=text_request(), headers=idem())
    assert response.status_code == 402
    assert response.get_json()["error"]["details"] == {"balance": 0, "required": 11}


def test_new_period_replaces_old_plan_credits_without_rollover(app, make_user):
    user = make_user()
    give_plan(app, user, 1000, ref="period-1")
    give_purchased(app, user, 500)
    job = user.post("/api/generation-jobs", json=text_request(), headers=idem()).get_json()["job"]
    assert job["status"] in ("queued", "completed")
    assert parts(app, user) == (997, 500, 1497)
    give_plan(app, user, 1000, ref="period-2")
    assert parts(app, user) == (1000, 500, 1500)  # 997 expired, not 1997
    # Repeating the same period start (a retried webhook) changes nothing.
    give_plan(app, user, 1000, ref="period-2")
    assert parts(app, user) == (1000, 500, 1500)
    assert tx_types(app, user).count("plan_allowance") == 2


def test_refund_after_period_end_keeps_plan_credits_expired(app, make_user):
    user = make_user()
    give_plan(app, user, 30)
    give_purchased(app, user, 40)
    FakeAsyncVideoAdapter.stay_pending = True
    original = generation_service._enqueue_poll
    generation_service._enqueue_poll = lambda job: None
    try:
        # 50 reserved: 30 plan + 20 purchased.
        job = user.post("/api/generation-jobs", json=video_request(), headers=idem()).get_json()["job"]
        assert parts(app, user) == (0, 20, 20)
        expire_now(app, user)  # the billing period ends while the video is rendering
        assert user.post(f"/api/generation-jobs/{job['id']}/cancel").status_code == 200
    finally:
        generation_service._enqueue_poll = original
    # Purchased credits come back; the 30 plan credits are returned and expired again.
    assert parts(app, user) == (0, 40, 40)
    with app.app_context():
        refund = db.session.query(CreditTransaction).filter_by(reference=f"job:{job['id']}:refund").one()
        again = db.session.query(CreditTransaction).filter_by(reference=f"job:{job['id']}:refund:expire").one()
        assert (refund.plan_amount, refund.purchased_amount) == (30, 20)
        assert (again.tx_type.value, again.plan_amount) == ("expire", -30)


def test_refund_within_period_returns_plan_credits(app, make_user):
    user = make_user()
    give_plan(app, user, 100)
    FakeAsyncVideoAdapter.final = "fail"
    user.post("/api/generation-jobs", json=video_request(), headers=idem())
    assert parts(app, user) == (100, 0, 100)


def test_parallel_spending_across_both_parts_cannot_overspend(app, make_user):
    from tests.test_credit_safety import run_in_parallel

    user = make_user()
    give_plan(app, user, 10)
    give_purchased(app, user, 5)  # 15 in total: one 11-credit job fits, two do not
    app.config["MAX_ACTIVE_JOBS_PER_USER"] = 10
    try:
        codes = run_in_parallel(app, user.token, [f"race-{uuid.uuid4()}" for _ in range(6)])
    finally:
        app.config["MAX_ACTIVE_JOBS_PER_USER"] = 3
    assert sorted(codes) == [201, 402, 402, 402, 402, 402], codes
    # 11 reserved (10 plan + 1 purchased), 3 charged from plan, 8 back: plan 7, purchased 5.
    assert parts(app, user) == (7, 5, 12)


def test_package_purchase_is_lasting_and_subscription_is_expiring(app, client, make_user, fake_paystack):

    user = make_user()
    reference = checkout(user, code="small").get_json()["payment"]["reference"]
    fake_paystack.paid(reference, 500)
    assert user.post("/api/billing/confirm", json={"reference": reference}).get_json()["payment"]["status"] \
        == "succeeded"
    reference = checkout(user, item_type="subscription", code="starter").get_json()["payment"]["reference"]
    fake_paystack.paid(reference, 900, plan={"plan_code": "PLN_starter", "amount": 900, "currency": "USD",
                                             "interval": "monthly"}, customer="CUS_x")
    user.post("/api/billing/confirm", json={"reference": reference})
    account = user.get("/api/billing/overview").get_json()["credits"]
    assert account["purchased_balance"] == 200 and account["plan_balance"] == 300
    expires = datetime.fromisoformat(account["plan_credits_expire_at"])
    with app.app_context():
        from app.models import Payment
        paid_at = db.session.query(Payment).filter_by(reference=reference).one().paid_at
    # The plan credits last exactly one billing period from the payment.
    assert expires == paid_at.replace(month=paid_at.month % 12 + 1, year=paid_at.year + (paid_at.month == 12))
    expire_now(app, user)
    assert parts(app, user) == (0, 200, 200)


# ---- Free sign-up grant --------------------------------------------------------------------------

def _verify_latest(client) -> int:
    token = outbox[-1].get_content().split("token=")[1].split()[0]
    return client.post("/api/auth/verify-email", json={"token": token}).status_code


def _with_grant(app, amount=50, cap=200):
    app.config["SIGNUP_CREDIT_GRANT"] = amount
    app.config["SIGNUP_GRANT_DAILY_CAP"] = cap


def _reset_grant(app):
    app.config["SIGNUP_CREDIT_GRANT"] = 0
    app.config["SIGNUP_GRANT_DAILY_CAP"] = 200


def test_signup_grant_is_given_once_after_email_verification(app):
    _with_grant(app)
    try:
        client = app.test_client()
        session = register(client, "new.person@example.com")
        assert parts(app, session) == (0, 0, 0)  # nothing before the email is confirmed
        assert _verify_latest(client) == 200
        assert parts(app, session) == (0, 50, 50)  # lasting credits
        # A second verification email (resend) cannot grant again.
        session.post("/api/auth/resend-verification")
        with app.app_context():
            from app.models import User
            from app.services import auth_service

            user = db.session.get(User, session.id)
            assert auth_service.grant_signup_credits(user) is False  # direct retry is refused too
            db.session.commit()
        assert parts(app, session) == (0, 50, 50)
        assert tx_types(app, session) == ["grant"]
    finally:
        _reset_grant(app)


def test_signup_grant_parallel_retries_grant_once(app):
    _with_grant(app)
    try:
        client = app.test_client()
        session = register(client, "racer@example.com")
        barrier = threading.Barrier(5)
        results = []

        def worker():
            with app.app_context():
                from app.models import User
                from app.services import auth_service

                user = db.session.get(User, session.id)
                barrier.wait()
                try:
                    results.append(auth_service.grant_signup_credits(user))
                    db.session.commit()
                except Exception as exc:  # noqa: BLE001 — a loser of the race may hit the unique key
                    db.session.rollback()
                    results.append(type(exc).__name__)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        assert results.count(True) == 1, results
        assert parts(app, session) == (0, 50, 50)
        with app.app_context():
            assert db.session.query(SignupGrantClaim).count() == 1
    finally:
        _reset_grant(app)


def test_signup_grant_not_repeated_for_same_inbox_or_after_account_deletion(app):
    _with_grant(app)
    try:
        client = app.test_client()
        first = register(client, "Sam.Smith@gmail.com")
        assert _verify_latest(client) == 200
        assert parts(app, first)[2] == 50
        # Same Gmail inbox through a +alias and dots: no second grant.
        client2 = app.test_client()
        alias = register(client2, "samsmith+promo@googlemail.com")
        assert _verify_latest(client2) == 200
        assert parts(app, alias)[2] == 0
        # Deleting the account and signing up again with the same address: no second grant.
        assert first.delete("/api/me", json={"password": "Correct-Horse-42", "confirm": "DELETE"}).status_code == 204
        client3 = app.test_client()
        again = register(client3, "sam.smith@gmail.com")
        assert _verify_latest(client3) == 200
        assert parts(app, again)[2] == 0
        with app.app_context():
            claim = db.session.query(SignupGrantClaim).one()
            assert claim.user_id is None  # the claim outlives the deleted account
    finally:
        _reset_grant(app)


def test_signup_grant_daily_cap(app):
    _with_grant(app, cap=1)
    try:
        c1, c2 = app.test_client(), app.test_client()
        one = register(c1, "one@example.com")
        assert _verify_latest(c1) == 200
        two = register(c2, "two@example.com")
        assert _verify_latest(c2) == 200
        assert parts(app, one)[2] == 50 and parts(app, two)[2] == 0
    finally:
        _reset_grant(app)


def test_canonical_email():
    assert canonical_email("Sam.Smith+x@GoogleMail.com") == "samsmith@gmail.com"
    assert canonical_email("a.b+tag@example.com") == "a.b@example.com"


# ---- Provider safety blocks -------------------------------------------------------------------------

def test_safety_block_refunds_customer_and_records_aszda_cost(app, make_user):
    user = make_user(credits=200)
    FakeAsyncVideoAdapter.final = "safety"
    created = user.post("/api/generation-jobs", json=video_request(), headers=idem()).get_json()["job"]
    job = user.get(f"/api/generation-jobs/{created['id']}").get_json()["job"]
    assert job["status"] == "failed" and job["error"]["code"] == "content_refused"
    assert job["credits_charged"] == 0
    assert parts(app, user) == (0, 200, 200)  # full refund
    with app.app_context():
        cost = db.session.query(ProviderCost).one()
        assert cost.outcome == "safety_blocked" and cost.absorbed_by_aszda is True
        assert cost.usage == {"video_seconds": 5} and cost.credits_charged_to_customer == 0
        assert cost.provider_reported["failureCode"] == "SAFETY.OUTPUT.VIDEO"
        from app.models import AuditEvent

        assert db.session.query(AuditEvent).filter_by(action="generation.provider_cost_absorbed").count() == 1
    # Not retryable without changing the request.
    assert user.post(f"/api/generation-jobs/{job['id']}/retry", headers=idem()).status_code == 409


def test_safety_block_reported_twice_or_in_parallel_refunds_once(app, make_user):
    user = make_user(credits=200)
    FakeAsyncVideoAdapter.stay_pending = True
    original = generation_service._enqueue_poll
    generation_service._enqueue_poll = lambda job: None
    try:
        job = user.post("/api/generation-jobs", json=video_request(), headers=idem()).get_json()["job"]
        job_id = uuid.UUID(job["id"])
        assert parts(app, user)[2] == 150
        blocked = ProviderError("blocked", code="content_refused", absorbed_usage={"video_seconds": 5})
        barrier = threading.Barrier(4)

        def deliver():
            with app.app_context():
                barrier.wait()
                generation_service._handle_error(job_id, blocked, may_retry=False)

        threads = [threading.Thread(target=deliver) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        # A late duplicate poll result after the job is final changes nothing either.
        FakeAsyncVideoAdapter.stay_pending = False
        FakeAsyncVideoAdapter.final = "safety"
        with app.app_context():
            generation_service.poll_job(job_id)
            generation_service._handle_error(job_id, blocked, may_retry=False)
    finally:
        generation_service._enqueue_poll = original
    assert parts(app, user) == (0, 200, 200)
    assert tx_types(app, user).count("refund") == 1
    with app.app_context():
        assert db.session.query(ProviderCost).count() == 1
        assert db.session.get(GenerationJob, job_id).status.value == "failed"


def test_completed_jobs_record_provider_cost(app, make_user):
    from app.services import pricing

    pricing.set_override({**pricing._overrides, "fake-video:fake-motion": pricing.ModelPrice(
        credits_per_1000={"video_seconds": 10_000}, minimum_credits=5,
        provider_usd_per_1000={"video_seconds": 120})})
    user = make_user(credits=200)
    user.post("/api/generation-jobs", json=video_request(), headers=idem())
    with app.app_context():
        cost = db.session.query(ProviderCost).one()
        assert cost.outcome == "completed" and not cost.absorbed_by_aszda
        assert float(cost.estimated_usd) == 0.6 and cost.credits_charged_to_customer == 50
