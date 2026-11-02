# 001: Authentication: design

## Key decisions

| Decision | Choice | Why |
| --- | --- | --- |
| Session mechanism | Server-side sessions in the DB, opaque token in a cookie | Revocable instantly (logout everywhere, password reset), no JWT refresh logic, a natural fit for server-rendered HTMX pages |
| Token storage | SHA-256 of a 32-byte `secrets.token_urlsafe` value | A DB leak does not expose usable tokens. The tokens are high-entropy, so a fast hash is enough (no need for Argon2 here) |
| Password hashing | Argon2id via `argon2-cffi` with default parameters | Current OWASP recommendation. `check_needs_rehash` lets us upgrade parameters later |
| CSRF | `SameSite=Lax` cookie + JSON-only API bodies | Lax blocks the cookie on cross-site POSTs, and cross-site JSON requests need a CORS preflight we do not allow. HTML forms (spec 005) will add a CSRF token |
| Email links | Point to UI pages (`/auth/...`) that POST the token to the API | Email scanners prefetch GET links. A GET that consumes a token would burn magic links before the user clicks |
| Duplicate signup | `409 Conflict` | Reveals that an account exists. Accepted: it is standard UX for B2B SaaS. Login and reset flows stay enumeration-safe |
| Login rate limit | In-process sliding window per email | Zero dependencies for 1.0. It works per process, so multi-worker deployments get a Redis-backed limiter later (see product "Later") |
| Time | Injected `Clock` | Expiry logic is testable without sleeping or freezing libraries |

## Data model

```
users
  id                 UUID PK
  email              VARCHAR(320) UNIQUE NOT NULL   -- normalised lowercase
  password_hash      VARCHAR(255) NULL              -- NULL reserved for future OAuth-only users
  email_verified_at  TIMESTAMPTZ NULL
  is_active          BOOLEAN NOT NULL DEFAULT true
  created_at         TIMESTAMPTZ NOT NULL
  updated_at         TIMESTAMPTZ NOT NULL

sessions
  id            UUID PK
  user_id       UUID FK users(id) ON DELETE CASCADE, indexed
  token_hash    CHAR(64) UNIQUE NOT NULL
  created_at    TIMESTAMPTZ NOT NULL
  expires_at    TIMESTAMPTZ NOT NULL
  last_seen_at  TIMESTAMPTZ NOT NULL
  user_agent    VARCHAR(512) NULL
  ip_address    VARCHAR(64) NULL

auth_tokens
  id          UUID PK
  user_id     UUID FK users(id) ON DELETE CASCADE, indexed
  purpose     VARCHAR(32) NOT NULL   -- verify_email | password_reset | magic_link
  token_hash  CHAR(64) UNIQUE NOT NULL
  created_at  TIMESTAMPTZ NOT NULL
  expires_at  TIMESTAMPTZ NOT NULL
  used_at     TIMESTAMPTZ NULL
```

All timestamps are timezone-aware UTC. A `UTCDateTime` column type keeps them
aware on SQLite too, which drops tz info on read.

## Module layout

```
app/
  main.py               create_app(): settings, routers, lifespan
  core/
    config.py           Settings (pydantic-settings, env vars / .env)
    db.py               async engine, session factory, get_db dependency
    clock.py            Clock protocol + SystemClock
    security.py         password hashing, token generation and hashing
    ratelimit.py        SlidingWindowLimiter
  models/
    base.py             DeclarativeBase, UTCDateTime, mixins
    user.py             User
    auth.py             Session (UserSession), AuthToken, TokenPurpose
  email/
    sender.py           EmailMessage, EmailSender protocol, Console + Memory senders
    templates.py        builds the auth emails
  auth/
    schemas.py          Pydantic request/response models
    service.py          AuthService: all business rules, no HTTP
    deps.py             current_user / optional_user dependencies, cookie helpers
    router.py           /api/auth/* endpoints, a thin layer over AuthService
```

Routers only translate HTTP to service calls and service errors to status
codes. Business rules live in `AuthService`, so the HTML pages in spec 005
reuse it unchanged.

## API

All bodies are JSON. Errors use FastAPI's `{"detail": "..."}` shape.

| Method | Path | Body | Success | Errors | Req |
| --- | --- | --- | --- | --- | --- |
| POST | `/api/auth/register` | `email`, `password` | 201 `UserOut` + cookie | 409, 422 | 1.x |
| POST | `/api/auth/login` | `email`, `password` | 200 `UserOut` + cookie | 401, 403, 429 | 3.1, 3.2, 3.6, 3.7 |
| POST | `/api/auth/logout` | none | 204, cookie cleared | none | 3.4 |
| GET | `/api/auth/me` | none | 200 `UserOut` | 401 | 6.1 |
| POST | `/api/auth/verify-email` | `token` | 200 `UserOut` | 400 | 2.1, 2.2 |
| POST | `/api/auth/verify-email/resend` | none | 202 | 400, 401 | 2.4 |
| POST | `/api/auth/password-reset/request` | `email` | 202 | 422 | 4.1 |
| POST | `/api/auth/password-reset/confirm` | `token`, `password` | 204 | 400, 422 | 4.3, 4.4 |
| POST | `/api/auth/magic-link/request` | `email` | 202 | 422 | 5.1 |
| POST | `/api/auth/magic-link/confirm` | `token` | 200 `UserOut` + cookie | 400 | 5.3, 5.4 |
| POST | `/api/auth/change-password` | `current_password`, `new_password` | 204 | 400, 401, 422 | 6.2 |
| GET | `/health` | none | 200 `{"status": "ok"}` | none | none |

`UserOut` = `{id, email, email_verified, created_at}`.

## Flows

**Login**

1. Normalise the email and check the limiter. Over the limit → 429.
2. Load the user. If missing, verify against a dummy hash anyway so response
   time does not reveal which emails exist, then fail with 401.
3. Wrong password → record a failure, 401. Deactivated → 403.
4. Create the session row and set the cookie. Rehash the password if the Argon2
   parameters changed.

**One-time tokens (verify / reset / magic)**

1. `issue(user, purpose)`: mark earlier unused tokens of that purpose used
   (AUTH-7.2), store the hash of a new token, return the raw token for the email.
2. `consume(raw, purpose)`: look up by hash; it must match the purpose, be
   unused and unexpired, otherwise raise `InvalidToken` (→ 400). Set `used_at`.

**Session resolution** (dependency on every request)

Read the cookie, hash it, load the session joined with the user. If it is
missing, expired, or the user is inactive → anonymous. `last_seen_at` is
updated at most once per 5 minutes to avoid a write on every request.

## Email

`EmailSender.send(message)` is async. 1.0 ships `ConsoleEmailSender` (dev) and
`MemoryEmailSender` (tests). Resend/SMTP senders and background sending come
with spec 004. Links use `APP_URL`:

- `{APP_URL}/auth/verify-email?token=…`
- `{APP_URL}/auth/reset-password?token=…`
- `{APP_URL}/auth/magic-link?token=…`

## Configuration

| Env var | Default | Notes |
| --- | --- | --- |
| `APP_NAME` | `SaaS Starter` | used in emails |
| `APP_URL` | `http://localhost:8000` | base for email links |
| `ENVIRONMENT` | `development` | `development`, `test`, `production` |
| `DATABASE_URL` | `sqlite+aiosqlite:///./dev.db` | use `postgresql+asyncpg://…` in production |
| `SESSION_COOKIE_NAME` | `session` | |
| `SESSION_TTL_DAYS` | `30` | AUTH-3.3 |
| `COOKIE_SECURE` | `false` | must be `true` in production (enforced at startup) |
| `EMAIL_FROM` | `no-reply@example.com` | |
| `LOGIN_MAX_FAILURES` / `LOGIN_WINDOW_SECONDS` | `10` / `900` | AUTH-3.7 |
