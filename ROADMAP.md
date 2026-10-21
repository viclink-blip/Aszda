# ASZDA Studio — Roadmap

Legend: ✅ done in this milestone · 🟡 partly done · ⏳ planned · 🔒 blocked on a founder decision or credential

## Phase 1 — Architecture and foundation ✅
Repository structure, Flask app factory, config per environment, PostgreSQL + Alembic,
Next.js app, design system, Docker Compose, CI workflow, documentation.

## Phase 2 — Authentication and dashboard ✅
Registration, sign-in, rotating refresh sessions, email verification, password reset,
roles (user/admin), account settings and deletion, dashboard with real data only.

## Phase 3 — Creative workspace and projects ✅
Projects (create, rename, describe, duplicate, delete), characters, storyboard scenes with
ordering, asset uploads and previews, job history per project.

## Phase 4 — AI provider integration 🟡
- ✅ Provider-independent adapter interface and registry
- ✅ Anthropic Claude (story concept, script, characters, scene breakdown)
- ✅ OpenAI text-to-speech
- ✅ Runway video (`gen4.5`, `veo3.1_fast`; text-to-video and image-to-video)
- 🔒 Live verification of each provider with real keys (none were available during the build)
- ⏳ Image generation adapter (choose a provider; verify its docs)
- ⏳ ElevenLabs voices (current model list could not be verified during the build)
- ✗ OpenAI Sora was skipped: OpenAI scheduled the Sora API to shut down on 2026-09-24.

## Phase 5 — Video and animation workflows 🟡
- ✅ Video Studio; Animation Studio animates a character reference image into a clip
- ⏳ A dedicated animation provider/model kind: today Animation Studio uses a video model in
  image-to-video mode, so its jobs are recorded with kind `video`
- ⏳ Use scene descriptions + character sheets to pre-fill generation prompts automatically
- ⏳ Keep a consistent character look across scenes (provider reference features)

## Phase 6 — Voice and scene assembly ⏳
- ✅ Voice Studio (TTS) and audio assets
- ⏳ Assemble scenes + voice into one video (FFmpeg worker), timeline editor, export
- ⏳ Voice cloning — only with recorded consent, identity checks and abuse safeguards

## Phase 7 — Credits and billing 🟡
- ✅ Credit ledger, reservations, refunds, limits, admin grants, usage report
- 🔒 Final credit prices (founder decision) — the app ships with nothing priced
- 🔒 Payment provider choice (e.g. Paystack for M-Pesa/cards in Kenya, Stripe internationally)
- ⏳ Credit packages, subscriptions, receipts, webhook processing with signature checks

## Phase 8 — Testing, security, deployment 🟡
- ✅ 72 backend tests, lint, migration checks, security headers, rate limits, audit log
- ⏳ Frontend unit tests and browser end-to-end tests in CI
- ⏳ First production deployment (hosting choice), backups, monitoring, error tracking
- ⏳ External security review before public launch

## The next milestone (recommended)
1. Add real API keys in a staging environment and run one real job per provider; fix anything the
   live APIs reveal.
2. Decide credit prices and the payment provider; then build credit packages + webhooks.
3. "AI Film Director" v1: Claude produces a structured scene breakdown that is saved directly as
   characters and scenes in a project (structured output), ready for review.
4. Scene assembly worker (FFmpeg) to stitch clips and voice-over into an exportable MP4.
5. Deploy staging (API + worker + Postgres + Redis + S3-compatible storage) behind HTTPS.
