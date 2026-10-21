# Credits, pricing and usage limits

Credits are ASZDA's **internal usage units**. They are separate from real money: a future payment
(once a payment provider is chosen) will *buy* credits, recorded as a `purchase` ledger entry.

## The ledger
Every change to a balance writes a row to `credit_transactions` in the same database transaction,
so the balance always equals the sum of the ledger.

| Type | Sign | When |
|---|---|---|
| `grant` | + | An admin (or the sign-up grant) gives credits |
| `purchase` | + | *(future)* credits bought through a verified payment |
| `reserve` | − | A job is queued: its maximum estimated cost is held |
| `release` | + | A job succeeded: the unused part of the reservation comes back |
| `refund` | + | A job failed or was cancelled: the reservation comes back (minus usage the provider actually billed) |
| `adjustment` | ± | An admin correction, with a reason |

Each entry has a unique `reference` (`job:<id>:reserve`, `job:<id>:refund`, ...). The database
rejects a second entry with the same reference, so retries can never double-charge or double-refund.
Balances are changed under a row lock, so two parallel requests cannot spend the same credits.

## Pricing file
Nothing is priced by default — a model without a price **cannot be used**. Prices are a business
decision, so they live in a JSON file you control:

```json
{
  "models": {
    "anthropic:claude-opus-5-5": {
      "credits_per_1000": {"input_tokens": 1, "output_tokens": 5},
      "minimum_credits": 1,
      "provider_usd_per_1000": {"input_tokens": 0.004, "output_tokens": 0.02}
    }
  }
}
```

- `credits_per_1000` — credits per 1,000 units of each usage metric the adapter reports
  (tokens, characters, video seconds...). Cost is rounded **up** to a whole credit.
- `minimum_credits` — smallest charge per job.
- `provider_usd_per_1000` — *optional*: what the provider charges you, used only in the admin usage
  report as an **estimate**. Leave it out unless you have verified the provider's price.

Start from `backend/pricing.example.json` (placeholder numbers, **not approved prices**), set
`ASZDA_PRICING_FILE`, restart API and worker, and run `flask --app wsgi aszda check-pricing`.

### Worked example
Claude job with "maximum length 4,000 tokens" and a 1,200-character prompt:
- Estimate ≈ 850 input + 4,000 output tokens → ⌈0.85 × 1 + 4 × 5⌉ = **21 credits reserved**.
- Claude actually uses 650 input + 1,800 output → ⌈0.65 + 9⌉ = **10 credits charged**,
  **11 released**.

## Limits (enforced on the server)
`ASZDA_MAX_CREDITS_PER_JOB`, `ASZDA_MAX_ACTIVE_JOBS_PER_USER`, `ASZDA_DAILY_JOB_LIMIT`,
`ASZDA_MONTHLY_CREDIT_LIMIT`, plus a verified email (`ASZDA_REQUIRE_VERIFIED_EMAIL`) and rate
limits on job creation. The browser never decides a cost or a balance.

## Failure and refund rules
| Situation | Charged |
|---|---|
| Rejected before queuing (invalid, unpriced, no credits, over a limit) | nothing, no reservation |
| Provider error, nothing billed | 0 — full refund |
| Provider refused the content but billed tokens (e.g. Claude refusal) | the reported usage only |
| Temporary error → automatic retry (only before anything reached the provider) | charged once at most |
| Provider took longer than `ASZDA_PROVIDER_MAX_POLL_MINUTES` | 0 — cancelled at provider if possible, refunded |
| User cancelled | 0 — refunded |
| Success | actual usage, never more than reserved |

> Note for video providers: Runway reports a cost on failed tasks. ASZDA does not pass provider
> failures on to users. Watch the admin usage report for provider-side costs you absorb.

## Payments

Paystack checkout for plans and credit packages is built; see [BILLING.md](BILLING.md). Prices are in
USD (with KES shown only as a labelled reference at the fixed rate of 133), payments are verified
for the exact amount and currency before any credits are granted, and a paid purchase adds a
`purchase` ledger entry exactly once. Checkout is switched off until the Paystack account is
confirmed to accept USD.
