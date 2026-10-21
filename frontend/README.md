# ASZDA Studio — web frontend

The browser app for ASZDA Studio: marketing site, sign-in, the signed-in studio
(projects, storyboard, studios, credits, settings) and the admin area.
It talks only to the Flask API in `../backend`.

## Stack

| Package | Version |
| --- | --- |
| Next.js (App Router, Turbopack) | 16.4.2 |
| React / React DOM | 19.3.0 |
| TypeScript (strict) | 5.9 |
| Tailwind CSS (v4, `@tailwindcss/turbopack`) | 4.3.3 |
| Radix UI (dialog, dropdown menu, tabs) | 1.3 / 2.2 / 1.2 |
| lucide-react (icons) | 1.61 |
| react-markdown (safe rendering of AI text) | 10.1 |

Node.js 20.9 or newer is required (developed on Node 22).

## Setup

```bash
cp .env.example .env.local   # ASZDA_API_URL=http://localhost:5000
npm install
npm run dev                  # http://localhost:3000
```

Start the API first (see `../backend`). For local development with emails printed
to the console and jobs run in-process:

```bash
cd ../backend
ASZDA_ENV=development ASZDA_MAIL_BACKEND=console ASZDA_CELERY_EAGER=true \
  .venv/bin/flask --app wsgi run --port 5000
```

## Commands

| Command | What it does |
| --- | --- |
| `npm run dev` | Development server with hot reload |
| `npm run lint` | ESLint (Next.js core-web-vitals + TypeScript rules) |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run build` | Production build |
| `npm start` | Serve the production build (after `npm run build`) |

## How it fits together

- **API proxy.** `next.config.ts` rewrites `/api/*` to `ASZDA_API_URL`, so the
  browser only ever talks to this site (same origin). The HttpOnly refresh cookie
  and the CSRF header work without CORS.
- **Auth.** The access token is kept in memory only (`src/lib/api.ts`,
  managed by `src/lib/auth.tsx`). On page load, and when a request fails with an
  expired token, the app calls `/api/auth/refresh` once (shared between parallel
  requests) and retries. `/app/*` is guarded on the client; the API enforces it.
- **Generation.** Settings forms are built from `/api/providers` (each model's
  `fields`). Unavailable models are shown disabled with the reason. Every submit
  gets an `Idempotency-Key`, reused only when retrying after a network error.
  Jobs are polled every 3 s until they finish (`src/hooks/use-job-polling.ts`).
- **Theme.** Colour tokens are CSS variables in `src/app/globals.css`; light/dark
  is set on `<html data-theme>` by a tiny inline script before first paint.

## Folders

```
src/app/            routes: (marketing), (auth), app/ (signed in), app/admin/
src/components/ui/  design system: Button, Field, Input, Dialog, Tabs, Toast, ...
src/components/     feature components (projects, generation, assets, admin, ...)
src/hooks/          useApi, useJobPolling, useModels, useDebounced
src/lib/            api client, types (mirror backend serializers), auth, formatting
```

## Before launch

- Replace the placeholder contact address `hello@aszda.example` (`src/lib/product.ts`).
- The Privacy Policy and Terms are drafts pending legal review.
