"""Currency, pricing and Paystack payment tests. Paystack is always mocked: no real
network call or payment happens."""

import hashlib
import hmac
import json
from decimal import Decimal

import pytest

from app.billing import catalog as catalog_mod
from app.billing import paystack
from app.billing.catalog import CatalogError, parse_catalog
from app.billing.money import Money, MoneyError, convert_minor, format_money
from app.extensions import db
from app.models import CreditAccount, CreditTransaction, Payment, PaymentStatus, Subscription
from app.services import payment_service

SECRET = "sk_test_aszda_unit_tests"

# The founder's prices (US cents) and the expected KES reference at 133 KES per USD.
SUBSCRIPTIONS = {"free": (0, "KSh 0"), "starter": (900, "KSh 1,197"), "creator": (1900, "KSh 2,527"),
                 "pro_studio": (4900, "KSh 6,517"), "studio_max": (9900, "KSh 13,167")}
PACKAGES = {"small": (500, "KSh 665"), "medium": (1000, "KSh 1,330"), "large": (2500, "KSh 3,325"),
            "professional": (5000, "KSh 6,650")}


# ---- Money and currency ------------------------------------------------------------------

@pytest.mark.parametrize("usd_cents,kes", [(900, "KSh 1,197"), (1900, "KSh 2,527"),
                                           (4900, "KSh 6,517"), (9900, "KSh 13,167")])
def test_required_subscription_conversions(usd_cents, kes):
    # $9 x 133 = KSh 1,197 ... computed in integer cents with Decimal, no floats.
    assert format_money(convert_minor(usd_cents, Decimal("133")), "KES") == kes


@pytest.mark.parametrize("usd_cents,kes", [(500, "KSh 665"), (1000, "KSh 1,330"),
                                           (2500, "KSh 3,325"), (5000, "KSh 6,650")])
def test_required_package_conversions(usd_cents, kes):
    assert format_money(convert_minor(usd_cents, Decimal("133")), "KES") == kes


def test_format_money():
    assert format_money(900, "USD") == "$9"
    assert format_money(0, "USD") == "$0"
    assert format_money(950, "USD") == "$9.50"
    assert format_money(905, "USD") == "$9.05"
    assert format_money(1234567, "USD") == "$12,345.67"
    assert format_money(-500, "USD") == "-$5"
    assert format_money(119700, "KES") == "KSh 1,197"
    assert Money(900, "USD").as_dict() == {"amount_minor": 900, "currency": "USD", "formatted": "$9"}
    with pytest.raises(MoneyError):
        Money(9.0, "USD")  # floats are never money
    with pytest.raises(MoneyError):
        Money(900, "EUR")


def test_conversion_rounds_half_up_to_whole_cents():
    assert convert_minor(1, Decimal("133.5")) == 134  # 133.5 cents -> 134
    assert convert_minor(3, Decimal("0.5")) == 2      # 1.5 -> 2 (not banker's rounding)


def test_reference_rate_is_configurable_and_validated(app):
    from app.billing.money import reference_rate, usd_with_reference

    with app.app_context():
        app.config["USD_TO_KES_REFERENCE_RATE"] = "140"
        try:
            assert usd_with_reference(900)["reference"]["formatted"] == "KSh 1,260"
            assert usd_with_reference(900)["formatted"] == "$9"  # USD never changes
            app.config["USD_TO_KES_REFERENCE_RATE"] = "abc"
            with pytest.raises(MoneyError):
                reference_rate()
            app.config["USD_TO_KES_REFERENCE_RATE"] = "-1"
            with pytest.raises(MoneyError):
                reference_rate()
        finally:
            app.config["USD_TO_KES_REFERENCE_RATE"] = "133"


def test_catalog_rejects_unsafe_prices():
    with pytest.raises(CatalogError):
        parse_catalog({"credit_packages": [{"code": "x", "name": "X", "price_usd_cents": 9.99, "credits": 1}]})
    with pytest.raises(CatalogError):
        parse_catalog({"credit_packages": [{"code": "x", "name": "X", "price_usd_cents": "500", "credits": 1}]})
    with pytest.raises(CatalogError):
        parse_catalog({"credit_packages": [{"code": "x", "name": "X", "price_usd_cents": 0, "credits": 1}]})
    with pytest.raises(CatalogError):
        parse_catalog({"plans": [{"code": "p", "name": "P", "price_usd_cents": 900, "interval": "year"}]})
    with pytest.raises(CatalogError):
        parse_catalog({"plans": [{"code": "p", "name": "P", "price_usd_cents": 900,
                                  "paystack_plan_code": "not-a-plan"}]})


def test_shipped_catalog_has_the_founders_prices(app):
    catalog_mod.set_override(None)
    with app.app_context():
        shipped = catalog_mod.get_catalog()
    assert {p.code: p.price_usd_cents for p in shipped.plans} == {k: v[0] for k, v in SUBSCRIPTIONS.items()}
    assert {p.code: p.price_usd_cents for p in shipped.credit_packages} == {k: v[0] for k, v in PACKAGES.items()}


def test_public_catalog_shows_usd_first_with_labelled_kes(client):
    catalog_mod.set_override(None)
    data = client.get("/api/billing/catalog").get_json()
    assert data["currency"]["display_currency"] == "USD"
    assert data["currency"]["reference_currency"] == "KES"
    assert data["currency"]["usd_to_kes_reference_rate"] == "133"
    plans = {p["code"]: p for p in data["plans"]}
    for code, (cents, kes) in SUBSCRIPTIONS.items():
        price = plans[code]["price"]
        assert price["currency"] == "USD" and price["amount_minor"] == cents
        assert price["formatted"] == f"${cents // 100}"
        assert price["reference"]["formatted"] == kes and price["reference"]["currency"] == "KES"
        assert "Reference only" in price["reference"]["label"]
        assert plans[code]["interval"] == "month"
    packages = {p["code"]: p for p in data["credit_packages"]}
    for code, (cents, kes) in PACKAGES.items():
        assert packages[code]["price"]["amount_minor"] == cents
        assert packages[code]["price"]["reference"]["formatted"] == kes
    assert data["checkout"]["enabled"] is False


# ---- Fake Paystack -------------------------------------------------------------------------

class FakePaystack:
    """Records calls and answers like Paystack's API (shapes from the official spec)."""

    def __init__(self):
        self.calls = []
        self.transactions = {}       # reference -> verify data
        self.plans = {}              # plan code -> plan data
        self.subscriptions = {}      # SUB code -> subscription data
        self.initialize_error = None
        self.verify_down = False

    def __call__(self, method, path, body=None):
        self.calls.append((method, path, body))
        if path == "/transaction/initialize":
            if self.initialize_error:
                raise paystack.PaystackError(self.initialize_error, status_code=400)
            return {"authorization_url": f"https://checkout.paystack.com/{body['reference']}",
                    "access_code": "ac_test", "reference": body["reference"]}
        if path.startswith("/transaction/verify/"):
            if self.verify_down:
                raise paystack.PaystackError("timeout", retryable=True)
            reference = path.rsplit("/", 1)[1]
            if reference not in self.transactions:
                raise paystack.PaystackError("Transaction reference not found", status_code=404)
            return self.transactions[reference]
        if path.startswith("/plan/"):
            return self.plans[path.rsplit("/", 1)[1]]
        if path.startswith("/subscription/") and method == "GET":
            return self.subscriptions[path.rsplit("/", 1)[1]]
        if path == "/subscription/disable":
            return {}
        raise AssertionError(f"unexpected Paystack call {method} {path}")

    def paid(self, reference, amount, currency="USD", status="success", plan=None, customer="CUS_test"):
        self.transactions[reference] = {
            "id": 5551234, "status": status, "reference": reference, "amount": amount, "currency": currency,
            "paid_at": "2026-10-21T10:00:00.000Z", "channel": "card", "gateway_response": "Approved",
            "customer": {"email": "x@example.com", "customer_code": customer},
            "plan": plan,
        }


@pytest.fixture()
def fake_paystack(app, monkeypatch):
    fake = FakePaystack()
    monkeypatch.setattr(paystack, "_request", fake)
    app.config["PAYSTACK_SECRET_KEY"] = SECRET
    app.config["PAYSTACK_USD_ENABLED"] = True
    catalog_mod.set_override(parse_catalog({
        "plans": [
            {"code": "free", "name": "Free", "price_usd_cents": 0},
            {"code": "starter", "name": "Starter", "price_usd_cents": 900, "monthly_credits": 300,
             "paystack_plan_code": "PLN_starter"},
            {"code": "creator", "name": "Creator", "price_usd_cents": 1900, "monthly_credits": None,
             "paystack_plan_code": "PLN_creator"},
        ],
        "credit_packages": [
            {"code": "small", "name": "Small", "price_usd_cents": 500, "credits": 200},
            {"code": "medium", "name": "Medium", "price_usd_cents": 1000, "credits": None},
        ],
    }))
    fake.plans["PLN_starter"] = {"plan_code": "PLN_starter", "amount": 900, "currency": "USD", "interval": "monthly"}
    yield fake
    app.config["PAYSTACK_SECRET_KEY"] = ""
    app.config["PAYSTACK_USD_ENABLED"] = False
    catalog_mod.set_override(None)


def balance(app, user) -> int:
    with app.app_context():
        account = db.session.query(CreditAccount).filter_by(user_id=user.id).one_or_none()
        return account.balance if account else 0


def purchases(app, user) -> list[int]:
    with app.app_context():
        return [t.amount for t in db.session.query(CreditTransaction).filter_by(tx_type="purchase")]


def checkout(user, item_type="credit_package", code="small", **extra):
    return user.post("/api/billing/checkout", json={"item_type": item_type, "item_code": code, **extra})


def signed(app, client, event: dict, signature: str | None = None):
    raw = json.dumps(event).encode()
    sig = signature or hmac.new(SECRET.encode(), raw, hashlib.sha512).hexdigest()
    return client.post("/api/billing/paystack/webhook", data=raw, content_type="application/json",
                       headers={"x-paystack-signature": sig})


# ---- Checkout availability ------------------------------------------------------------------

def test_checkout_refused_without_paystack_key(app, make_user):
    user = make_user()
    response = checkout(user)
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "payments_not_configured"


def test_checkout_refused_until_usd_confirmed(app, make_user, fake_paystack):
    app.config["PAYSTACK_USD_ENABLED"] = False
    user = make_user()
    response = checkout(user)
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "usd_checkout_not_enabled"
    assert fake_paystack.calls == []  # Paystack never contacted, nothing charged in KES instead
    with app.app_context():
        assert db.session.query(Payment).count() == 0


def test_paystack_currency_rejection_is_reported_not_converted(app, make_user, fake_paystack):
    fake_paystack.initialize_error = "Currency not supported by merchant"
    user = make_user()
    response = checkout(user)
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "usd_checkout_rejected"
    initializes = [c for c in fake_paystack.calls if c[1] == "/transaction/initialize"]
    assert len(initializes) == 1 and initializes[0][2]["currency"] == "USD"  # no KES retry
    with app.app_context():
        assert db.session.query(Payment).one().status == PaymentStatus.FAILED


# ---- Price authority -------------------------------------------------------------------------

def test_server_decides_amount_and_currency(app, make_user, fake_paystack):
    user = make_user()
    response = checkout(user)
    assert response.status_code == 201, response.get_json()
    body = fake_paystack.calls[-1][2]
    assert body["amount"] == 500 and isinstance(body["amount"], int)
    assert body["currency"] == "USD"
    assert body["reference"].startswith("aszda-")
    assert body["callback_url"].endswith("/app/billing/complete")
    data = response.get_json()
    assert data["authorization_url"].startswith("https://checkout.paystack.com/")
    assert data["payment"]["price"]["formatted"] == "$5"
    assert data["payment"]["price"]["reference"]["formatted"] == "KSh 665"


@pytest.mark.parametrize("extra", [{"amount": 1}, {"currency": "KES"}, {"credits": 999999},
                                   {"exchange_rate": "1"}, {"price_usd_cents": 1}])
def test_client_price_manipulation_is_rejected(app, make_user, fake_paystack, extra):
    user = make_user()
    response = checkout(user, **extra)
    assert response.status_code == 422
    assert fake_paystack.calls == []


def test_unknown_or_unconfigured_items_are_refused(app, make_user, fake_paystack):
    user = make_user()
    assert checkout(user, code="mega").status_code == 404
    unpriced = checkout(user, code="medium")  # credits not decided yet
    assert unpriced.status_code == 409 and unpriced.get_json()["error"]["code"] == "credits_not_configured"
    assert checkout(user, item_type="subscription", code="free").status_code == 409
    assert checkout(user, item_type="subscription", code="creator").status_code == 409
    assert checkout(user, code="small; drop table").status_code == 422


# ---- Verification and fulfilment -------------------------------------------------------------

def test_verified_payment_grants_credits_exactly_once(app, client, make_user, fake_paystack):
    user = make_user()
    reference = checkout(user).get_json()["payment"]["reference"]
    fake_paystack.paid(reference, 500, "USD")
    first = user.post("/api/billing/confirm", json={"reference": reference})
    assert first.status_code == 200
    payment = first.get_json()["payment"]
    assert payment["status"] == "succeeded" and payment["credits_granted"] is True
    assert payment["amount_paid"]["formatted"] == "$5"
    # The browser callback again, plus a Paystack webhook for the same charge: no double credit.
    assert user.post("/api/billing/confirm", json={"reference": reference}).status_code == 200
    webhook = signed(app, client, {"event": "charge.success", "data": {"id": 5551234, "reference": reference}})
    assert webhook.status_code == 200
    assert balance(app, user) == 200
    assert purchases(app, user) == [200]
    verifies = [c for c in fake_paystack.calls if c[1].startswith("/transaction/verify/")]
    assert len(verifies) == 1  # once final, Paystack is not asked again


@pytest.mark.parametrize("amount,currency", [(499, "USD"), (50000, "USD"), (66500, "KES"), (500, "KES"),
                                             (500, "NGN")])
def test_wrong_amount_or_currency_gives_nothing(app, make_user, fake_paystack, amount, currency):
    user = make_user()
    reference = checkout(user).get_json()["payment"]["reference"]
    fake_paystack.paid(reference, amount, currency)
    payment = user.post("/api/billing/confirm", json={"reference": reference}).get_json()["payment"]
    assert payment["status"] == "mismatch"
    assert payment["credits_granted"] is False
    assert balance(app, user) == 0


def test_failed_or_pending_payment_gives_nothing(app, make_user, fake_paystack):
    user = make_user()
    ref1 = checkout(user).get_json()["payment"]["reference"]
    fake_paystack.paid(ref1, 500, status="failed")
    assert user.post("/api/billing/confirm", json={"reference": ref1}).get_json()["payment"]["status"] == "failed"
    ref2 = checkout(user).get_json()["payment"]["reference"]
    # Not paid yet: Paystack has no record -> stays pending.
    assert user.post("/api/billing/confirm", json={"reference": ref2}).get_json()["payment"]["status"] == "pending"
    assert balance(app, user) == 0


def test_payments_are_private(app, make_user, fake_paystack):
    owner, other = make_user(), make_user()
    data = checkout(owner).get_json()["payment"]
    fake_paystack.paid(data["reference"], 500)
    assert other.post("/api/billing/confirm", json={"reference": data["reference"]}).status_code == 404
    assert other.get(f"/api/billing/payments/{data['id']}").status_code == 404
    assert other.get("/api/billing/payments").get_json()["total"] == 0
    assert balance(app, other) == 0
    receipt = owner.get(f"/api/billing/payments/{data['id']}").get_json()
    assert receipt["payment"]["price"]["formatted"] == "$5"
    assert receipt["currency"]["display_currency"] == "USD"


# ---- Webhooks -------------------------------------------------------------------------------

def test_webhook_signature_required(app, client, make_user, fake_paystack):
    user = make_user()
    reference = checkout(user).get_json()["payment"]["reference"]
    fake_paystack.paid(reference, 500)
    event = {"event": "charge.success", "data": {"id": 1, "reference": reference}}
    assert signed(app, client, event, signature="0" * 128).status_code == 401
    assert client.post("/api/billing/paystack/webhook", json=event).status_code == 401
    assert balance(app, user) == 0
    assert signed(app, client, event).get_json()["outcome"] == "payment_succeeded"
    assert balance(app, user) == 200


def test_webhook_body_is_not_trusted_for_money(app, client, make_user, fake_paystack):
    user = make_user()
    reference = checkout(user).get_json()["payment"]["reference"]
    fake_paystack.paid(reference, 100)  # Paystack's API says only $1 was paid
    forged = {"event": "charge.success",
              "data": {"id": 9, "reference": reference, "amount": 500, "currency": "USD", "status": "success"}}
    assert signed(app, client, forged).get_json()["outcome"] == "payment_mismatch"
    assert balance(app, user) == 0


def test_duplicate_webhook_is_ignored(app, client, make_user, fake_paystack):
    user = make_user()
    reference = checkout(user).get_json()["payment"]["reference"]
    fake_paystack.paid(reference, 500)
    event = {"event": "charge.success", "data": {"id": 777, "reference": reference}}
    assert signed(app, client, event).get_json()["outcome"] == "payment_succeeded"
    assert signed(app, client, event).get_json()["outcome"] == "duplicate"
    assert purchases(app, user) == [200]


def test_webhook_retry_after_temporary_failure(app, client, make_user, fake_paystack):
    user = make_user()
    reference = checkout(user).get_json()["payment"]["reference"]
    fake_paystack.paid(reference, 500)
    fake_paystack.verify_down = True
    event = {"event": "charge.success", "data": {"id": 888, "reference": reference}}
    assert signed(app, client, event).status_code == 503  # Paystack will retry
    fake_paystack.verify_down = False
    assert signed(app, client, event).get_json()["outcome"] == "payment_succeeded"
    assert balance(app, user) == 200


# ---- Subscriptions ----------------------------------------------------------------------------

def test_subscription_lifecycle(app, client, make_user, fake_paystack):
    user = make_user()
    response = checkout(user, item_type="subscription", code="starter")
    assert response.status_code == 201, response.get_json()
    init = [c for c in fake_paystack.calls if c[1] == "/transaction/initialize"][-1][2]
    assert init["plan"] == "PLN_starter" and init["amount"] == 900 and init["currency"] == "USD"
    reference = response.get_json()["payment"]["reference"]

    plan_obj = {"plan_code": "PLN_starter", "amount": 900, "currency": "USD", "interval": "monthly"}
    fake_paystack.paid(reference, 900, plan=plan_obj, customer="CUS_maya")
    confirmed = user.post("/api/billing/confirm", json={"reference": reference}).get_json()
    assert confirmed["payment"]["status"] == "succeeded"
    assert balance(app, user) == 300
    overview = user.get("/api/billing/overview").get_json()
    assert overview["subscription"]["plan_code"] == "starter"
    assert overview["subscription"]["status"] == "active"
    assert overview["plan"]["price"]["formatted"] == "$9"
    assert overview["plan"]["price"]["reference"]["formatted"] == "KSh 1,197"
    # Already subscribed -> no second subscription.
    assert checkout(user, item_type="subscription", code="starter").status_code == 409

    # Paystack creates the subscription; we fetch it to get the cancel token.
    fake_paystack.subscriptions["SUB_maya"] = {
        "subscription_code": "SUB_maya", "email_token": "tok_secret", "status": "active",
        "next_payment_date": "2026-11-21T10:00:00.000Z", "plan": plan_obj,
        "customer": {"customer_code": "CUS_maya"}}
    created = signed(app, client, {"event": "subscription.create", "data": {"subscription_code": "SUB_maya"}})
    assert created.get_json()["outcome"] == "subscription_linked"

    # A renewal charged by Paystack with its own reference.
    fake_paystack.paid("T_renewal_1", 900, plan=plan_obj, customer="CUS_maya")
    renewal = {"event": "charge.success", "data": {"id": 99, "reference": "T_renewal_1", "plan": plan_obj,
                                                   "customer": {"customer_code": "CUS_maya"}}}
    assert signed(app, client, renewal).get_json()["outcome"] == "renewal_succeeded"
    assert balance(app, user) == 600
    assert signed(app, client, renewal).get_json()["outcome"] == "duplicate"
    assert balance(app, user) == 600

    # Cancel: Paystack is told, the plan stops renewing.
    cancelled = user.post("/api/billing/subscription/cancel")
    assert cancelled.status_code == 200
    assert cancelled.get_json()["subscription"]["status"] == "non_renewing"
    assert ("POST", "/subscription/disable", {"code": "SUB_maya", "token": "tok_secret"}) in fake_paystack.calls
    assert "tok_secret" not in json.dumps(user.get("/api/billing/overview").get_json())


def test_subscription_refused_when_paystack_plan_differs(app, make_user, fake_paystack):
    fake_paystack.plans["PLN_starter"] = {"plan_code": "PLN_starter", "amount": 119700, "currency": "KES",
                                          "interval": "monthly"}
    user = make_user()
    response = checkout(user, item_type="subscription", code="starter")
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "plan_mismatch"
    assert not [c for c in fake_paystack.calls if c[1] == "/transaction/initialize"]


def test_subscription_paid_with_wrong_plan_gives_nothing(app, make_user, fake_paystack):
    user = make_user()
    reference = checkout(user, item_type="subscription", code="starter").get_json()["payment"]["reference"]
    fake_paystack.paid(reference, 900, plan={"plan_code": "PLN_other"})
    confirmed = user.post("/api/billing/confirm", json={"reference": reference}).get_json()
    assert confirmed["payment"]["status"] == "mismatch"
    with app.app_context():
        assert db.session.query(Subscription).count() == 0
    assert balance(app, user) == 0


def test_admin_payments_view(app, make_user, fake_paystack):
    admin, user = make_user(admin=True), make_user()
    checkout(user)
    assert user.get("/api/admin/payments").status_code == 403
    data = admin.get("/api/admin/payments").get_json()
    assert data["total"] == 1 and data["items"][0]["price"]["formatted"] == "$5"
    assert data["checkout"]["enabled"] is True


def test_no_float_money_in_payment_service():
    import inspect

    source = inspect.getsource(payment_service)
    assert "float(" not in source
