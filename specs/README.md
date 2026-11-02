# Specs

This project uses **spec-driven development**. Every feature goes through three
documents before (and while) code is written:

1. `requirements.md`: user stories plus acceptance criteria in EARS notation
   (`WHEN <trigger> THE SYSTEM SHALL <response>`). Each criterion has an ID
   (e.g. `AUTH-3.2`), and tests reference those IDs.
2. `design.md`: data model, module layout, API contract, security decisions and
   the trade-offs behind them.
3. `tasks.md`: an ordered checklist of small implementation steps, each linked
   to the requirement IDs it satisfies.

Rules:

- Change the spec first, then the code. A PR that changes behaviour without
  touching the spec is incomplete.
- Every acceptance criterion has at least one test whose docstring names its ID.
- Out-of-scope ideas go to the "Later" list in `000-product/overview.md`, not
  into the current feature.

| Spec | Status |
| --- | --- |
| [000-product](000-product/overview.md) | living document |
| [001-auth](001-auth/requirements.md) | implemented, awaiting first test run |
| 002-organizations | planned |
| 003-billing (Paddle) | planned |
| 004-background-jobs-and-email | planned |
| 005-web-ui (Jinja + HTMX) | planned |
| 006-deploy | planned |
