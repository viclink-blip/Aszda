"""Credit safety under real concurrency: several requests at the same moment, each in its
own thread with its own database session, exactly like parallel web requests."""

import threading
import uuid

from app.extensions import db
from app.models import CreditAccount, CreditTransaction, GenerationJob

# FakeTextAdapter with max_output_tokens=1000 reserves 11 credits per job (see test_generation.py).
COST = 11


def text_request():
    return {"provider": "fake-text", "model": "fake-writer", "kind": "text",
            "params": {"prompt": "A fox who sells shoes", "max_output_tokens": 1000}}


def run_in_parallel(app, token: str, keys: list[str]) -> list[int]:
    """Fire one POST per key at the same instant; return the HTTP status codes."""
    barrier = threading.Barrier(len(keys))
    results: list[int] = [0] * len(keys)

    def worker(index: int, key: str):
        client = app.test_client()
        barrier.wait()
        response = client.post("/api/generation-jobs", json=text_request(),
                               headers={"Authorization": f"Bearer {token}", "Idempotency-Key": key})
        results[index] = response.status_code

    threads = [threading.Thread(target=worker, args=(i, k)) for i, k in enumerate(keys)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return results


def ledger_state(app, user_id):
    with app.app_context():
        account = db.session.query(CreditAccount).filter_by(user_id=user_id).one()
        ledger = sum(t.amount for t in db.session.query(CreditTransaction).filter_by(account_id=account.id))
        jobs = db.session.query(GenerationJob).filter_by(user_id=user_id).count()
        return account.balance, ledger, jobs


def test_parallel_requests_cannot_spend_the_same_credits(app, make_user):
    # Enough for exactly one reservation (11) but not two (22).
    user = make_user(credits=15)
    app.config["MAX_ACTIVE_JOBS_PER_USER"] = 10
    try:
        codes = run_in_parallel(app, user.token, [f"race-{uuid.uuid4()}" for _ in range(6)])
    finally:
        app.config["MAX_ACTIVE_JOBS_PER_USER"] = 3
    assert sorted(codes) == [201, 402, 402, 402, 402, 402], codes
    balance, ledger, jobs = ledger_state(app, user.id)
    assert jobs == 1
    assert balance == ledger >= 0
    assert balance == 15 - 3  # one job ran: 11 reserved, 3 charged, 8 released


def test_parallel_duplicates_with_one_key_create_one_job(app, make_user):
    user = make_user(credits=100)
    key = f"dup-{uuid.uuid4()}"
    codes = run_in_parallel(app, user.token, [key] * 5)
    assert codes.count(201) == 1 and codes.count(200) == 4, codes
    balance, ledger, jobs = ledger_state(app, user.id)
    assert jobs == 1
    assert balance == ledger == 100 - 3


def test_no_generation_without_enough_credits(app, make_user):
    user = make_user(credits=COST - 1)
    response = user.post("/api/generation-jobs", json=text_request(),
                         headers={"Idempotency-Key": f"k-{uuid.uuid4()}"})
    assert response.status_code == 402
    assert response.get_json()["error"]["details"] == {"balance": COST - 1, "required": COST}
    balance, ledger, jobs = ledger_state(app, user.id)
    assert (balance, jobs) == (COST - 1, 0)


def test_parallel_duplicates_never_deadlock(app, make_user):
    """Regression: a duplicate request used to insert its job while holding the account lock,
    waiting on the original job's row while the worker settling that job waited for the same
    lock (PostgreSQL deadlock -> HTTP 500). Repeated to make the race likely."""
    for _ in range(20):
        user = make_user(credits=100)
        codes = run_in_parallel(app, user.token, [f"dup-{uuid.uuid4()}"] * 5)
        assert sorted(codes) == [200, 200, 200, 200, 201], codes
        assert ledger_state(app, user.id) == (97, 97, 1)
