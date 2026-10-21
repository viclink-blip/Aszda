# Data we store, and how deletion works

*Draft for review by a legal advisor before launch. Relevant laws include Kenya's Data Protection
Act, 2019 (and registration with the Office of the Data Protection Commissioner where required),
the EU/UK GDPR for users there, and the laws of other markets ASZDA serves.*

## What is stored
| Data | Where | Why |
|---|---|---|
| Email, password hash (never the password), display name, optional language/country | PostgreSQL | Account |
| Sessions: device user-agent, IP address, times | PostgreSQL | Security, sign-out |
| Projects, characters, scenes, prompts and settings | PostgreSQL | The user's work |
| Uploaded and generated media | Object storage (private) | The user's work |
| Generation jobs: provider, model, usage, result text | PostgreSQL | Showing results, billing, support |
| Credit ledger | PostgreSQL | Accurate balances, disputes |
| Audit events (actions, IP, times; never secrets) | PostgreSQL | Security investigation |

Prompts and reference media are sent to the AI provider chosen for a job (Anthropic, OpenAI or
Runway) to produce the result; their own data policies apply. The privacy policy must name them.

## Account deletion
`DELETE /api/me` (password + typing DELETE) **immediately and permanently** removes the user and,
through database cascades, their profile, sessions, tokens, projects, characters, scenes, assets,
jobs, credit account and ledger, then deletes their stored files. Audit events are kept for
security investigations: their link to the user row is cleared (`SET NULL`), but events still hold
the former user ID as plain text (`target_id`) and IP addresses. They contain no email, name or content,
and should be removed on the audit retention schedule below.

> Before payments go live, decide how long financial records must be kept (tax law) and switch
> payment records to anonymisation instead of deletion.

## Project and asset deletion
Deleting a project deletes its characters, scenes, assets and stored files. Jobs remain with the
project reference cleared, so credit history stays consistent.

## Suggested retention schedule (to confirm)
- Revoked/expired sessions and used tokens: delete after 90 days (scheduled cleanup job — not built yet).
- Audit events: 1 year.
- Orphaned files: `flask --app wsgi aszda cleanup-storage`.
