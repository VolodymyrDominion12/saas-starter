# Product overview

## What it is

A paid FastAPI SaaS starter kit. A buyer clones it and has a production-ready
foundation for a subscription product: auth, teams, billing, background jobs,
email, admin, and deployment. It saves them 2 to 4 weeks of work.

## Positioning

"Launch a paid SaaS from any country over a weekend."

- Billing through **merchant-of-record** providers (Paddle first, Lemon Squeezy
  next), so it works where Stripe is not available and VAT is handled for you.
- Pure Python stack: FastAPI + server-rendered Jinja/HTMX, so no separate JS app
  is needed to ship.
- Small, readable codebase with a spec for every feature, so buyers can
  understand and change it.

## Target buyer

Python developers and indie hackers who want to ship a B2B micro-SaaS and do not
want to rebuild auth and billing for the tenth time.

## Version 1.0 scope

| Area | Spec | Included in 1.0 |
| --- | --- | --- |
| Auth | 001 | Email + password, email verification, password reset, magic link, server-side sessions |
| Organizations | 002 | Orgs, invitations, owner/member roles |
| Billing | 003 | Paddle subscriptions, webhooks, plan gating, customer portal link |
| Jobs & email | 004 | ARQ worker + scheduler, Resend/SMTP transactional email |
| Web UI | 005 | Landing, auth pages, dashboard, billing page (Jinja + HTMX + Tailwind) |
| Ops | 006 | Docker Compose, Alembic, CI, one-command deploy (Coolify / Fly.io) |
| Admin | 006 | SQLAdmin |

## Later (not in 1.0)

- Google and GitHub OAuth (planned as 1.1, right after 1.0)
- 2FA (TOTP)
- Lemon Squeezy and Stripe billing adapters
- Usage-based billing
- Fine-grained permissions
- React frontend variant
- Rate limiting backed by Redis (1.0 ships a simple in-process limiter)

## Technical baseline

- Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Alembic
- PostgreSQL in production. SQLite (aiosqlite) is supported for tests and quick local runs.
- `uv` for dependency management, `ruff` for lint and format, `pytest` for tests
