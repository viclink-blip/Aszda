# Credits, pricing and usage limits

Credits are ASZDA's **internal usage units**. They are separate from real money: a verified
Paystack payment *grants* credits through a ledger entry.

## Two kinds of credits (policy approved 2026-10-22)

| | Plan credits | Purchased credits |
|---|---|---|
| Come from | A subscription's monthly allowance | Credit packages, the one-time sign-up grant, admin grants |
| Expire | **At the end of the billing period they belong to; no rollover** | Never |
| Spent | **First** (they expire soonest) | After plan credits |

- **Balances.** `credit_accounts` keeps `plan_balance`, `purchased_balance` and `plan_credits_expire_at`. The database enforces `balance = plan_balance + purchased_balance`. Every ledger row records its split (`plan_amount` and `purchased_amount`, which add up to `amount`).
- **New billing period.** A subscription payment (first or renewal) expires the previous period's unused plan credits, recorded as `expire`. It then adds the new allowance (`plan_allowance`), valid until the period end. Paystack's `next_payment_date` moves that end date when it differs.
- **When expiry happens.** Expiry is applied whenever a balance is read or spent, so an ended period's credits can never be used. The hourly scheduler also tidies up stored balances.
- **Generation charges.** A job's actual cost comes from its reservation, plan credits first. Anything unused goes back to the part it came from.
- **Refunds after a period ends.** Suppose the billing period ends while a job is running. Plan credits returned afterwards are returned and **expired again immediately**, and both rows are recorded. A refund therefore never turns expired plan credits into lasting ones. Purchased credits are always returned.
- **Credits held before this change.** All existing credits were migrated as purchased credits (never expire), so nobody lost anything.
- **What customers see.** The Credits and Billing pages show both balances, when plan credits expire, and the spending order.

## Free sign-up credits

- **Amount and timing.** 50 credits (`ASZDA_SIGNUP_CREDIT_GRANT`) are given **once**, when a new account first confirms its email address. A real inbox is needed. They are purchased-type credits, so they never expire.
- **Once per inbox.** The claim is stored per *canonical* address: lower-case, "+tag" removed, and dots removed for Gmail. The claim is kept when the account is deleted, so deleting and recreating an account, or using an alias of the same inbox, gets nothing.
- **Duplicate events.** Retries, a second verification link, and parallel verification requests cannot grant twice. The claim row is unique, and so is the ledger reference `signup:<user>`.
- **Daily cap.** At most `ASZDA_SIGNUP_GRANT_DAILY_CAP` grants (200) are given per UTC day. This is a soft runaway guard; parallel sign-ups can exceed it by a few.
- **Not covered.** There is no disposable-email blocklist and no per-IP limit; the web app's proxy does not forward the client IP yet.

## The ledger
Every change to a balance writes a row to `credit_transactions` in the same database transaction,
so the balance always equals the sum of the ledger.

| Type | Sign | When |
|---|---|---|
| `grant` | + | An admin, or the one-time sign-up grant, gives credits (purchased, never expire) |
| `purchase` | + | A credit package paid through a verified payment (purchased, never expire) |
| `plan_allowance` | + | A subscription billing period starts (plan credits, valid until the period ends) |
| `expire` | − | Unused plan credits removed at the end of their billing period |
| `reserve` | − | A job is queued: its maximum estimated cost is held |
| `release` | + | A job succeeded: the unused part of the reservation comes back |
| `refund` | + | A job failed or was cancelled: the reservation comes back (minus usage the provider actually billed) |
| `adjustment` | ± | An admin correction, with a reason |

Each entry has a unique `reference` (`job:<id>:reserve`, `job:<id>:refund`, ...). The database
rejects a second entry with the same reference, so retries can never double-charge or double-refund.
Balances are changed under a row lock, so two parallel requests cannot spend the same credits.

## Where credit prices are set

1. **Admin → Pricing** (database, audited) — the normal place. Generation credit costs per model,
   monthly credits and usage limit per plan, credits per package. USD prices are read-only there.
2. **Pricing file** (`ASZDA_PRICING_FILE`, see `backend/pricing.example.json`) — a fallback for
   models with no admin price. An admin price always wins; a disabled admin price blocks the model.
3. `flask --app wsgi aszda pricing-apply <file> [--yes]` loads a whole pricing document (generation
   costs plus plan and package credits) into Admin → Pricing. Without `--yes` it only previews.

A model with no price cannot be used. The proposed values are in
[CREDIT_PRICING_PROPOSAL.md](CREDIT_PRICING_PROPOSAL.md) and `backend/pricing.approved.json`
(approved 2026-10-22, **not active until the verification checklist is done and it is applied**).

Pricing-file format (also used for generation entries in a pricing document):

```json
{
  "models": {
    "anthropic:claude-opus-5-5": {
      "credits_per_1000": {"input_tokens": 1.1, "output_tokens": 5.3},
      "minimum_credits": 1,
      "provider_usd_per_1000": {"input_tokens": 0.004, "output_tokens": 0.02}
    }
  }
}
```

- `credits_per_1000` — credits per 1,000 units of each usage metric the adapter reports
  (tokens, characters, video seconds...). Cost is rounded **up** to a whole credit.
- `minimum_credits` — smallest charge per job.
- `provider_usd_per_1000` — *optional*: what the provider charges you, used only in margin reports.

Each job stores the price it started with, so changing a price never affects jobs already running.

### Worked example
Claude job with "maximum length 4,000 tokens" and a 1,200-character prompt:
- Estimate ≈ 850 input + 4,000 output tokens → ⌈0.85 × 1 + 4 × 5⌉ = **21 credits reserved**.
- Claude actually uses 650 input + 1,800 output → ⌈0.65 + 9⌉ = **10 credits charged**,
  **11 released**.

## Limits (enforced on the server)
A per-plan monthly limit (Admin → Pricing) replaces `ASZDA_MONTHLY_CREDIT_LIMIT` for subscribers.
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
| Provider's safety system blocked it (Runway `SAFETY.*`, OpenAI `moderation_blocked`, Google safety filter) | 0 — full refund. Runway still bills ASZDA, so that cost is recorded in `provider_costs` as `absorbed_by_aszda` and audited |
| User cancelled | 0 — refunded |
| Lost queue message or crashed worker (stuck job) | 0 — the sweeper fails and refunds it (every 5 minutes) |
| Success | actual usage, never more than reserved |

## Provider costs and reconciliation

Each settled job writes one `provider_costs` row (unique per job, so repeated polls cannot record it twice). It holds:
- the outcome: completed, safety block, or failed but billed;
- the usage;
- the **estimated** USD, from the provider prices entered in Admin → Pricing, or empty when none are entered;
- any figure the provider itself reported, such as OpenAI image tokens or Anthropic tokens;
- the credits charged to the customer;
- whether ASZDA absorbed the cost.

Admin → Providers → Provider costs compares these with the credits charged. They are estimates, not invoices. Compare them with each provider's billing dashboard.

## Concurrency and duplicates (tested)

- Six parallel requests with credit for one job: one runs, five get 402. The test also proves the row locks are what prevent it: with the locks removed, two jobs got through.
- Parallel requests with the same Idempotency-Key create one job and one reservation. They are re-checked under the account lock, which also prevents a database deadlock with the worker settling the original job (regression test, repeated 20 times).
- Spending across plan and purchased credits, refunds, sign-up grants and safety-block refunds are each tested for duplicates and parallel delivery.

## Payments

Paystack checkout for plans and credit packages is built; see [BILLING.md](BILLING.md). Prices are in
USD (with KES shown only as a labelled reference at the fixed rate of 133), payments are verified
for the exact amount and currency before any credits are granted, and a paid purchase adds a
`purchase` ledger entry exactly once. Checkout is switched off until the Paystack account is
confirmed to accept USD.
