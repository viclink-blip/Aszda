# Billing: prices, currency and Paystack payments

## Status (2026-10-21, re-checked 2026-10-22)

| Item | Status |
|---|---|
| USD prices for plans and credit packages, KES reference amounts | Done, shown everywhere prices appear |
| Credits per plan / per package | **Not decided** (`null` in `backend/billing_catalog.json`), so nothing is on sale yet |
| Paystack checkout, verification, webhooks, subscriptions, receipts | Built and covered by automated tests with a **mocked** Paystack |
| Real Paystack transaction (test or live) | **Not done yet**: no ASZDA Paystack keys exist yet, and the build environment could not reach `api.paystack.co` |
| USD support on ASZDA's Paystack account | **Not verified**. Checkout stays closed until it is (`ASZDA_PAYSTACK_USD_ENABLED=false`) |

## Currency rules

Configuration (`backend/app/config.py`):

```
DISPLAY_CURRENCY = "USD"
REFERENCE_CURRENCY = "KES"
USD_TO_KES_REFERENCE_RATE = 133      # env: ASZDA_USD_TO_KES_REFERENCE_RATE
```

- **Prices are shown and charged in US dollars.**
- **KES amounts are reference only.** They are calculated with the founder's fixed rate of
  133 KES per USD. That rate is a business setting, not a live market rate. KES amounts are always
  labelled "reference" and never replace the USD price or change what Paystack charges. ASZDA
  does not use any live exchange-rate service.
- **Money is stored in integer minor units** (cents). Conversions use Python `Decimal` with
  half-up rounding (`backend/app/billing/money.py`); floats are never used for money.
- **One formatter each side** produces the same output: `backend/app/billing/money.py`
  (`format_money`) and `frontend/src/lib/money.ts` (`formatMoney`). Examples: `$9`, `$9.50`,
  `KSh 1,197`.

## Prices (single source: `backend/billing_catalog.json`)

| Plan | USD per month | KES reference (×133) |
|---|---|---|
| Free | $0 | KSh 0 |
| Starter | $9 | KSh 1,197 |
| Creator | $19 | KSh 2,527 |
| Pro Studio | $49 | KSh 6,517 |
| Studio Max | $99 | KSh 13,167 |

| Credit package | USD | KES reference (×133) |
|---|---|---|
| Small | $5 | KSh 665 |
| Medium | $10 | KSh 1,330 |
| Large | $25 | KSh 3,325 |
| Professional | $50 | KSh 6,650 |

Prices are in the catalog as US cents (`"price_usd_cents": 900`). The web app reads them through
`GET /api/billing/catalog`, so no component contains a price. To change a price, edit the
catalog and restart the API and worker.

**Still to decide:**
- `monthly_credits` for each paid plan and `credits` for each package. Until a number is set,
  that item shows "to be announced" and cannot be bought.
- `paystack_plan_code` for each paid plan (see "Enabling subscriptions").

## How a payment works

1. **Choose.** The signed-in user picks an item. The browser sends only `item_type` and
   `item_code`. Any `amount`, `currency`, `credits` or rate in the request is rejected (422).
2. **Server sets the price.** The server reads the price from the catalog and creates a
   `pending` payment row. The row stores the expected USD amount in cents and the credits to
   grant, plus a unique reference (`aszda-<hex>`).
3. **Paystack initialize.** The server calls Paystack *Initialize Transaction* with
   `amount` (cents), `currency: "USD"`, the reference, and `callback_url = /app/billing/complete`.
   For plans it also sends `plan: PLN_...`, after first checking that the Paystack plan's
   amount, currency and interval match the catalog.
4. **Pay.** The user pays on Paystack's page. ASZDA never sees card details.
5. **Return.** Paystack returns the user to `/app/billing/complete?reference=...`. The page asks
   the server to confirm; the redirect itself proves nothing.
6. **Verify.** The server calls *Verify Transaction* and gives value only if all of these hold:
   - `status == "success"`
   - `amount` == the expected cents
   - `currency == "USD"`
   - the reference matches
   - for plans, the plan code matches
7. **Grant once.** Credits are added through a `purchase` ledger entry with the unique reference
   `payment:<id>:credits`. The payment row is locked while this happens. The browser
   confirmation and the webhook can both arrive, Paystack may retry, and credits are still
   granted exactly once.
8. **Mismatch.** If money arrives with the wrong amount, currency or plan, the payment is marked
   `mismatch` ("Under review"). Nothing is granted, and the admin sees it under
   Admin → Payments.
9. **Webhooks.** Paystack calls `POST /api/billing/paystack/webhook`.
   - **Signature:** the `x-paystack-signature` header is checked (HMAC-SHA512 of the raw body
     with the secret key). Requests without a valid signature are rejected.
   - **Duplicates:** each event is stored once (`payment_events`) and repeats are ignored.
   - **Trust:** money is never taken from the webhook body. `charge.success` always triggers the
     Verify API.
   - **Retries:** if Paystack's API is down, the webhook answers with an error so that Paystack
     retries later.
   - **Events handled:** `charge.success` (purchases and renewals), `subscription.create`,
     `subscription.not_renew`, `subscription.disable` and `invoice.payment_failed`.

## Paystack USD: what was verified, and the evidence

Paystack's websites could not be opened from the build environment. These facts come from
Paystack's **official** GitHub sources:
- [PaystackOSS/openapi](https://github.com/PaystackOSS/openapi), `paystack.yaml`, June 2026
- [PaystackOSS/doc-code-snippets](https://github.com/PaystackOSS/doc-code-snippets), October 2026

Facts marked *(search summary)* come only from search-engine summaries of paystack.com and must
be confirmed on paystack.com.

**Confirmed from the spec and samples:**
- The `currency` field accepts `GHS, KES, NGN, ZAR, USD`, and amounts are in the smallest unit.
- `POST /transaction/initialize`, `GET /transaction/verify/{reference}`, `GET /plan/{code}`,
  `GET /subscription/{code}` and `POST /subscription/disable` exist with the fields used here.
- When `plan` is sent, it "would invalidate the value provided in amount".
- Webhook signature: HMAC-SHA512 hex of the raw body, in the `x-paystack-signature` header.

**From search summaries only:**
- Only Kenya- and Nigeria-based businesses can accept USD and be paid out in USD.
- USD is not enabled by default; it is requested from the Paystack dashboard.
- A transaction in a currency that isn't enabled fails with *"Currency not supported by
  merchant"*.
- The minimum USD transaction is $2.

**Not verified at all:**
- That **ASZDA's** account accepts and settles USD. No ASZDA Paystack account or key was
  available.
- That USD *plans* (subscriptions) are allowed for a Kenyan account. Re-checked on 2026-10-22:
  - The Plan API takes a `currency` field, but no official page lists which currencies plans accept.
  - Paystack's Kenya help pages say M-Pesa cannot be used for recurring payments, so subscriptions would be card-only.
  - Fees (search summaries of paystack.com/ke/pricing): 3.8% for international cards and for all cards in USD, 2.9% for local cards, 1.5% for M-Pesa. No separate conversion fee was found.
  - Webhooks are signed with `x-paystack-signature`, an HMAC-SHA512 of the raw body with the secret key. ASZDA already verifies this.

That is why checkout is off by default. ASZDA never falls back to charging KES: if Paystack refuses
USD, the user sees that no payment was taken and the attempt is recorded as failed.

## Enabling USD checkout (founder steps)

1. **Paystack account.** Create or activate the ASZDA Paystack business account (Kenya). In
   *Settings → Preferences*, request **USD** payments. In *Settings → Payouts Accounts*, add a
   **USD bank account**. Ask Paystack support to confirm in writing that USD is enabled and how it
   settles.
2. **Test key.** Put the **test** secret key in `.env`: `PAYSTACK_SECRET_KEY=sk_test_...`.
3. **Ask Paystack.** Run the check:
   ```bash
   flask --app wsgi aszda paystack-check --try-usd
   ```
   It creates (but does not charge) a $2.00 USD test transaction and prints Paystack's answer. If
   Paystack accepts USD, you'll see a checkout link. If it refuses, you'll see its message, for
   example "Currency not supported by merchant".
4. **Switch on.** Only after Paystack confirms USD, set `ASZDA_PAYSTACK_USD_ENABLED=true`.
5. **Decide credits.** Set the credit amounts in `billing_catalog.json`.
6. **Webhook.** In the Paystack dashboard, set the webhook URL to
   `https://<your-domain>/api/billing/paystack/webhook`.
7. **Restart** the API and worker.

### Enabling subscriptions

For each paid plan:
1. Create a **monthly USD plan** in the Paystack dashboard with exactly the catalog amount
   (for example, Starter = 900 cents = $9.00).
2. Put its `PLN_...` code in `paystack_plan_code`.
3. Run `flask --app wsgi aszda paystack-check`. It reports whether each plan **MATCHES** the
   catalog.

If a plan doesn't match, checkout for it is refused.

Also run `flask --app wsgi aszda expire-subscriptions` once a day (cron or a scheduler). It ends
cancelled plans once their paid month is over.

## Testing payments (test mode)

1. Complete steps 1–7 above with the **test** key.
2. Sign in, open **Billing**, and buy the Small package.
3. On Paystack's test page, pay with Paystack's test card (*search summary*:
   `4084 0840 8408 4081`, CVV `408`, any future expiry). Use the card Paystack's test-payments
   page lists.
4. You return to *Payment received*. Check that:
   - **Billing → Payment history** shows the payment as **Paid**, $5 USD;
   - **Credits** shows a **Purchase** entry;
   - **Admin → Payments** shows Expected = Paid = $5 USD.
5. Try a subscription the same way. The Paystack dashboard should list the subscription, and
   **Billing** should show the plan as Active.
6. Cancel it on **Billing**. It should show "Cancelled — ends at the end of the paid month".
7. **Going live:** switch to the live key (`sk_live_...`) and live webhook URL, re-run
   `paystack-check`, then do one small real purchase and refund it from the Paystack dashboard if
   needed.

Production refuses to start with a test key unless `ASZDA_ALLOW_TEST_PAYMENTS=true`, which is for
staging only.

## Known limitations
- **Plan changes:** to change plan, cancel first and subscribe again. Upgrades and downgrades
  with proration are not built.
- **Refunds:** done in the Paystack dashboard. ASZDA does not yet process Paystack refund
  webhooks, so remove credits with an admin adjustment after refunding.
- **Plans give credits only:** a plan currently gives monthly credits and nothing else; no
  features are restricted by plan.
- **Account deletion:** this also deletes payment records today. Decide how long to keep
  financial records for tax law before launch (docs/DATA_RETENTION.md).
- **Tax:** there is no tax/VAT handling or formal tax invoice yet. The receipt is a payment receipt.
