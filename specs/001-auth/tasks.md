# 001: Authentication: tasks

Each task is small enough for one sitting (about an hour) and lists the
requirements it covers.

## Foundation

- [x] T1. Dependencies, `Settings`, async DB session, `create_app`, `/health`
- [x] T2. `Base`, `UTCDateTime`, timestamp mixin; Alembic configured for async engines
- [x] T3. Docker Compose (app + Postgres), Dockerfile, `.env.example`, ruff config

## Auth core

- [x] T4. `security.py`: Argon2id hash/verify/needs-rehash, token generate/hash (AUTH-1.5, 7.1)
- [x] T5. Models `User`, `UserSession`, `AuthToken` + initial migration
- [x] T6. Email sender protocol, console + memory senders, auth email templates (AUTH-7.3)
- [x] T7. `AuthService.register` (AUTH-1.1 to 1.5)
- [x] T8. One-time token issue/consume with invalidation (AUTH-2.2, 4.2, 5.2, 7.2)
- [x] T9. Email verification + resend (AUTH-2.x)
- [x] T10. Sessions: create, resolve, revoke; cookie helpers (AUTH-3.1, 3.3 to 3.6)
- [x] T11. Login with timing-safe miss + sliding-window limiter (AUTH-3.2, 3.7)
- [x] T12. Password reset request/confirm (AUTH-4.x)
- [x] T13. Magic link request/confirm (AUTH-5.x)
- [x] T14. `me` + change password (AUTH-6.x)
- [x] T15. Router wiring and error mapping

## Verification

- [x] T16. Tests per acceptance criterion (IDs in docstrings), written
- [ ] T16b. First full `uv run pytest` run on a machine with PyPI access; fix anything it finds
- [ ] T17. Run the migration against Postgres; smoke test with uvicorn

## Follow-ups (other specs)

- HTML pages for every flow, CSRF tokens for forms → 005
- Background email sending, Resend/SMTP → 004
- Expired session/token cleanup job → 004
