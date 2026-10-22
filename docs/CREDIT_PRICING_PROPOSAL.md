# Credit pricing (approved, not yet active)

**Status: APPROVED by the founder on 2026-10-22. NOT ACTIVE YET.** The values below are in
`backend/pricing.approved.json`. They take effect only after the verification checklist in
section 9 is complete and someone runs
`flask --app wsgi aszda pricing-apply pricing.approved.json --yes` (or enters the values in
Admin → Pricing). USD subscription and package prices are unchanged. The margins below are
estimates based on provider prices that are partly unverified; **they are not guaranteed.**

## 1. What generation exists today

| Feature | Studio | Provider and model | Integration status |
|---|---|---|---|
| Script and story writing | Script Studio | Anthropic `claude-opus-5-5` (Messages API, official SDK) | Built and tested with mocks. Reached the live API once with an invalid key (correctly rejected). **No successful real generation yet** (no key). |
| Voice (text to speech) | Voice Studio | OpenAI `gpt-4o-mini-tts`, `tts-1`, `tts-1-hd` | Built and tested with mocks. **Never called live.** |
| Video, from text or an image | Video Studio | Runway `gen4.5`, `veo3.1_fast` | Built and tested with mocks. **Never called live.** |
| Animation | Animation Studio | Same Runway models (animates a character's reference image) | Not a separate integration: it is image-to-video. |
| Image generation | — | none | **Not implemented.** No provider, no price. |

None of the three provider keys is configured, so no generation can run today.

## 2. Provider prices (what ASZDA pays)

| Model | Provider price | Source and confidence |
|---|---|---|
| Claude `claude-opus-5-5` | $4 per 1M input tokens, $20 per 1M output tokens | Anthropic pricing page, **opened directly** 2026-10-22 |
| OpenAI `tts-1` | $15 per 1M characters | OpenAI model page, **search summary only**; the page reportedly marks it deprecated |
| OpenAI `tts-1-hd` | $30 per 1M characters | Same as above |
| OpenAI `gpt-4o-mini-tts` | $0.60 per 1M text tokens + $12 per 1M audio tokens | Search summary. **Cost per character is not documented.** A third party estimates about $0.015 per minute; this proposal assumes **$0.03 per 1,000 characters** (about double) to be safe. |
| Runway `gen4.5` | 12 API credits per second = **$0.12/s** (1 API credit = $0.01) | Runway API pricing page, search summary only |
| Runway `veo3.1_fast` | **$0.10/s** without audio, **$0.15/s** with audio | Same as above |
| Paystack Kenya, international card | 3.8% per transaction | paystack.com/ke/pricing, search summary only (local card 2.9%, M-Pesa 1.5%) |

**Verify every "search summary only" price** against the provider's own page before going live.
Each provider page could not be opened from the build environment.

## 3. How credits work today (audited)

| Step | What happens | Where in the code |
|---|---|---|
| Estimate | The model's worst-case usage, times the credit rates, rounded up (minimum per job) | `pricing.ModelPrice.credits_for` |
| Check | The account row is locked, then: enough credits (402 otherwise), per-job cap, active jobs, daily cap, monthly cap | `generation_service.create_job` |
| Reserve | The estimate is taken from the balance and a `reserve` ledger row is written, in the same transaction as the job | `credit_service.reserve_for_job` |
| Charge | When the job finishes, actual usage is priced at the **price saved when the job started** (never above the reservation) | `generation_service._complete` |
| Release or refund | The unused part is returned as `release` (success) or `refund` (failure or cancel). Usage a provider bills on a refusal is charged. | `credit_service.settle_job` |
| Record | Every change is a ledger row with a unique reference (`job:<id>:reserve` and so on), so nothing can be applied twice | `credit_transactions` table |

**Proven by tests:**
- No generation without enough credits.
- Six parallel requests with credit for one: exactly one job runs. A mutation test showed two jobs got through when the row locks were removed.
- Five parallel duplicates with one Idempotency-Key create one job and one charge.
- Failed and cancelled jobs are refunded exactly once.

**Gaps found in this audit, now fixed:**
1. **Stuck jobs kept credits reserved forever.** A lost queue message or a crashed worker left the
   reservation in place. An automatic sweeper (every 5 minutes, and `aszda reap-stuck-jobs`) now:
   - fails and refunds jobs queued for over 30 minutes;
   - fails and refunds jobs running with no provider task for over 45 minutes;
   - resumes polling of provider tasks whose polling was lost. Past the deadline this cancels the
     task at the provider and refunds.
2. **The monthly usage limit was one global number (5,000).** That would have blocked Studio Max
   subscribers from using their allowance. Limits are now set per plan.
3. **Pricing was file-only.** Admin → Pricing now edits generation costs, plan allowances and
   package credits (audited). USD prices stay read-only.

## 4. Proposed credit value and generation costs

**Rule:** every generation earns at least **262.5 credits per $1 of provider cost**. At the
cheapest credit ASZDA sells (Studio Max, $0.00792 per credit), after the 3.8% card fee, that
leaves at least a **50% gross margin**, even if a customer spends every credit on the most
expensive generation.

| Generation | Credit cost | Example job | Credits | Provider cost |
|---|---|---|---|---|
| Video, Runway gen4.5 | **32 per second** (minimum 64) | 5-second clip | 160 | $0.60 |
| | | 10-second clip | 320 | $1.20 |
| Video, Veo 3.1 Fast | **27 per second**, or **40 per second with audio** (minimum 108) | 8 seconds, no audio | 216 | $0.80 |
| | | 8 seconds with audio | 320 | $1.20 |
| Script, Claude Opus 5.5 | **1.1 per 1,000 input tokens**, **5.3 per 1,000 output tokens** | Draft: 1.5k in / 4k out | 23 | $0.086 |
| | | Longest: 3k in / 16k out | 89 | $0.332 |
| Voice, tts-1 | **4 per 1,000 characters** (minimum 2) | About 1 minute (1,000 characters) | 4 | $0.015 |
| Voice, tts-1-hd and gpt-4o-mini-tts | **8 per 1,000 characters** (minimum 2) | About 1 minute | 8 | $0.03 (assumed) |
| Image | — | Not implemented | — | — |

Video is priced on its own, per second and per model, because it costs far more than text: one
10-second clip costs as much as about 14 script drafts. The largest single job (320 credits) stays
under the per-job safety cap of 500.

## 5. Proposed plan allowances and package credits

| Item | Price | Credits | Price per credit | ≈ gen4.5 5-second clips | ≈ script drafts | Monthly usage limit |
|---|---|---|---|---|---|---|
| **Starter** | $9/month | **1,000** | $0.0090 | 6 | 43 | 5,000 |
| **Creator** | $19/month | **2,200** | $0.0086 | 13 | 95 | 10,000 |
| **Pro Studio** | $49/month | **6,000** | $0.0082 | 37 | 260 | 25,000 |
| **Studio Max** | $99/month | **12,500** | $0.0079 | 78 | 543 | 50,000 |
| **Small** | $5 | **500** | $0.0100 | 3 | 21 | — |
| **Medium** | $10 | **1,000** | $0.0100 | 6 | 43 | — |
| **Large** | $25 | **2,600** (+4%) | $0.0096 | 16 | 113 | — |
| **Professional** | $50 | **5,300** (+6%) | $0.0094 | 33 | 230 | — |

Plans give more credits per dollar than packages, so subscribing is the better deal. The monthly
usage limit caps spending including bought credits, as an abuse and runaway-cost guard.

## 6. Estimated maximum costs and gross margins

Revenue is shown after the 3.8% Paystack international card fee. Costs are provider costs only;
hosting, storage, email and support are not included.

**Worst case.** The customer uses every credit on the generation with the highest provider cost per
credit ($0.00375 per credit, computed by Admin → Pricing):

| Item | Net revenue | Maximum provider cost | Gross margin |
|---|---|---|---|
| Starter | $8.66 | $3.75 | **56.7%** |
| Creator | $18.28 | $8.25 | **54.9%** |
| Pro Studio | $47.14 | $22.50 | **52.3%** |
| Studio Max | $95.24 | $46.88 | **50.8%** |
| Small | $4.81 | $1.88 | **61.0%** |
| Medium | $9.62 | $3.75 | **61.0%** |
| Large | $24.05 | $9.75 | **59.5%** |
| Professional | $48.10 | $19.88 | **58.7%** |

**Typical case (assumption).** Subscribers use 60% of their monthly credits. The margin then rises
to about 74% (Starter) and 70% (Studio Max).

These figures are checked by an automated test (`test_proposal_keeps_at_least_50_percent_margin`).

## 7. Decisions (recorded 2026-10-22)

The founder decided:
1. **Credit costs and quantities:** approved as listed in sections 4 and 5.
2. **Plan credits expire at the end of each billing period** (no rollover). Purchased package credits never expire. Built: see [CREDITS.md](CREDITS.md).
3. **Runway safety blocks:** the customer is refunded in full, and the Runway charge is recorded as an ASZDA cost. Built.
4. **Free plan:** 50 credits once per eligible new account, given on email confirmation, once per inbox. Built.
5. **Voice models:** keep them until the provider shuts them down. OpenAI lists all current TTS models for shutdown on 2027-01-06; ASZDA shows this and refuses them from that date. A Realtime-API voice adapter is needed before then.

Original questions, kept for reference:

## 7a. Questions that were put to the founder

1. **Approve or adjust** the credit costs (section 4) and the credit quantities (section 5).
2. **Unused monthly credits.**
   - *Today:* plan credits never expire and pile up month to month.
   - *Recommendation:* unused plan credits expire at renewal; bought package credits never expire.
   - *Status:* this is **not built yet**, and needs your approval.
3. **Runway moderation failures.**
   - *Today:* Runway charges for generations its safety filter blocks, while ASZDA refunds the user
     in full. Repeated blocked prompts would cost ASZDA money.
   - *Recommendation:* for safety-blocked videos only, charge the credits Runway billed.
   - *Status:* not changed until you decide.
4. **Free plan.**
   - *Today:* the Free plan has 0 credits, so Free users cannot generate.
   - *Option:* a one-time sign-up grant (for example 50 credits ≈ $0.19 maximum cost) with
     verified email required. The setting exists (`ASZDA_SIGNUP_CREDIT_GRANT`) and is 0 today.
5. **gpt-4o-mini-tts cost.** Its per-character cost is an assumption. Review it after the first
   real invoice, using Admin → Usage.
6. **tts-1 and tts-1-hd** are reportedly deprecated by OpenAI. Consider offering only gpt-4o-mini-tts.

## 8. How to apply after approval

```bash
cd backend
flask --app wsgi aszda pricing-apply pricing.approved.json        # preview (changes nothing)
flask --app wsgi aszda pricing-apply pricing.approved.json --yes  # apply (audited)
```

After that, every value can be changed in **Admin → Pricing** without a restart. Payments stay
switched off (`ASZDA_PAYSTACK_USD_ENABLED=false`) until USD is confirmed with Paystack.

## 9. Verification before activating for customers

Do not apply `pricing.approved.json` in production until each line is checked:

- [ ] Anthropic Opus 5.5: $4 / $20 per 1M tokens. Opened directly on 2026-10-22; re-check on the day of activation.
- [ ] Runway gen4.5 price per second, on Runway's own pricing page.
  - **The two sources conflict.** The pricing page says 12 credits/s ($0.12/s); the models page says "from $0.15/s" (both search summaries).
  - At $0.15/s and 32 credits/s, the worst-case margins drop to: Starter 45.9%, Creator 43.6%, Pro Studio 40.3%, Studio Max 38.5%, Small/Medium 51.3%, Large 49.3%, Professional 48.3%.
  - To keep at least 50% at $0.15/s, gen4.5 would need about **40 credits per second** (minimum 80). This is not applied; it needs your decision.
- [ ] Runway veo3.1_fast at $0.10/s and $0.15/s with audio, and whether Runway charges `SAFETY.OUTPUT.*` failures. Its docs are ambiguous; ASZDA budgets them as charged and absorbs them.
- [ ] OpenAI tts-1 / tts-1-hd at $15 / $30 per 1M characters, and the gpt-4o-mini-tts assumption of $0.03 per 1,000 characters. Check the latter after the first invoice.
- [ ] Paystack Kenya fees: 3.8% international cards and USD, 2.9% local cards, 1.5% M-Pesa (search summaries).
- [ ] Paystack USD and recurring billing for this merchant account (see [BILLING.md](BILLING.md)).
- [ ] Image and Google Veo models: **no credit prices yet.** Price them only after their provider prices are confirmed.

How the arithmetic was checked:
- **Automated test.** `test_proposal_keeps_at_least_50_percent_margin` recomputes every item from the approved file.
- **Independent recomputation.** A separate Decimal calculation outside the application reproduced every margin in section 6 exactly, and the $0.15/s figures above.
- **Exact job prices.** Tests check the credits for each reference job: gen4.5 5 s = 160, 10 s = 320; Veo 8 s = 216, or 320 with audio; script draft = 23; one minute of tts-1 = 4.
