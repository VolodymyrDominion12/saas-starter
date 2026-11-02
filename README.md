# SaaS Starter (FastAPI)

A FastAPI foundation for a paid SaaS: auth, teams, merchant-of-record billing,
background jobs and email. Built spec-first: every feature has a spec in
[`specs/`](specs/README.md), and tests reference its acceptance criteria.

**Status:** spec 001 (authentication API) is implemented. See the
[roadmap](specs/README.md) for what comes next.

## Quick start

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/).

```bash
uv sync                       # install dependencies (creates .venv and uv.lock)
cp .env.example .env          # local settings (SQLite by default)
uv run alembic upgrade head   # create tables
uv run uvicorn app.main:create_app --factory --reload
```

Open http://localhost:8000/docs for the interactive API. In development, emails
(verification, reset, magic link) are printed to the console, so copy the token
from the log.

### With Docker and PostgreSQL

```bash
docker compose up --build
```

This starts Postgres, runs migrations, and serves the app on port 8000.

## Tests and lint

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Tests use a temporary SQLite database, an in-memory email outbox, and a fake
clock, so expiry rules are tested without waiting.

## Project layout

```
app/
  core/      settings, database, clock, password/token security, rate limiter
  models/    SQLAlchemy models (users, sessions, auth tokens)
  email/     email sender interface + templates
  auth/      service (business rules), router (HTTP), deps, schemas
alembic/     migrations
specs/       requirements, design and tasks for every feature
tests/       one test module per requirement group
```

## Auth API (spec 001)

| Method | Path | What it does |
| --- | --- | --- |
| POST | `/api/auth/register` | Sign up, start a session, send a verification email |
| POST | `/api/auth/login` | Log in with email + password |
| POST | `/api/auth/logout` | End the current session |
| GET | `/api/auth/me` | Current user |
| POST | `/api/auth/verify-email` | Confirm the email with a token |
| POST | `/api/auth/verify-email/resend` | Send a new verification email |
| POST | `/api/auth/password-reset/request` | Email a reset link |
| POST | `/api/auth/password-reset/confirm` | Set a new password with a token |
| POST | `/api/auth/magic-link/request` | Email a login link |
| POST | `/api/auth/magic-link/confirm` | Log in with a token |
| POST | `/api/auth/change-password` | Change the password (logs out other devices) |

Security notes: server-side sessions (revocable), `HttpOnly` + `SameSite=Lax`
cookies, Argon2id passwords, SHA-256-hashed one-time tokens, enumeration-safe
login/reset/magic-link responses, and a failed-login rate limit. Details and
trade-offs are in [`specs/001-auth/design.md`](specs/001-auth/design.md).

## Development workflow

1. Write or update the spec (`requirements.md`, then `design.md`, then `tasks.md`).
2. Write tests that name the acceptance-criterion IDs in their docstrings.
3. Implement until the tests pass, then tick the tasks.
