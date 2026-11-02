# 001: Authentication: requirements

Status: implemented (API), awaiting the first full test run (see tasks T16b, T17). HTML pages for these flows are part of spec 005.

## Glossary

- **User**: a person with an account, identified by a unique email.
- **Session**: a server-side record that represents a logged-in browser. The
  browser holds an opaque token in a cookie.
- **One-time token**: a random secret sent by email for verification, password
  reset, or magic-link login. It is single-use and expires.

## User stories

- As a visitor, I want to sign up with email and password so I can use the product.
- As a user, I want to confirm my email so the product knows the address is mine.
- As a user, I want to log in and out, and stay logged in on my device.
- As a user who forgot my password, I want to reset it through my email.
- As a user, I want to log in with a link sent to my email, without a password.
- As a user, I want to see and change my account credentials.

## Acceptance criteria

### AUTH-1 Registration

- **AUTH-1.1** WHEN a visitor submits an email and a password of 8 to 128
  characters, THE SYSTEM SHALL create an unverified user, start a session for
  it, send a verification email, and respond `201` with the user.
- **AUTH-1.2** THE SYSTEM SHALL normalise emails (trim spaces, lowercase) before
  storing or comparing them.
- **AUTH-1.3** IF the email is already registered, THEN THE SYSTEM SHALL respond
  `409` and not change the existing account.
- **AUTH-1.4** IF the email is malformed or the password length is outside 8 to
  128 characters, THEN THE SYSTEM SHALL respond `422`.
- **AUTH-1.5** THE SYSTEM SHALL store passwords only as Argon2id hashes.

### AUTH-2 Email verification

- **AUTH-2.1** WHEN a valid, unexpired, unused verification token is submitted,
  THE SYSTEM SHALL mark the user's email as verified and mark the token used.
- **AUTH-2.2** IF a verification token is unknown, expired, already used, or of
  another purpose, THEN THE SYSTEM SHALL respond `400` and change nothing.
- **AUTH-2.3** Verification tokens SHALL expire 24 hours after issue.
- **AUTH-2.4** WHEN a logged-in, unverified user requests a new verification
  email, THE SYSTEM SHALL invalidate their previous verification tokens and
  send a new one. IF the user is already verified, THE SYSTEM SHALL respond
  `400`.

### AUTH-3 Login, logout, sessions

- **AUTH-3.1** WHEN a user submits a correct email and password, THE SYSTEM SHALL
  create a session and set the session cookie as `HttpOnly`, `SameSite=Lax`,
  `Path=/`, and `Secure` when `COOKIE_SECURE` is enabled.
- **AUTH-3.2** IF the email is unknown or the password is wrong, THEN THE SYSTEM
  SHALL respond `401` with the same message in both cases.
- **AUTH-3.3** Sessions SHALL expire 30 days after creation (configurable).
- **AUTH-3.4** WHEN a logged-in user logs out, THE SYSTEM SHALL delete the
  session and clear the cookie.
- **AUTH-3.5** WHEN a request carries an unknown or expired session token, THE
  SYSTEM SHALL treat it as anonymous. Protected endpoints SHALL respond `401`.
- **AUTH-3.6** IF the user is deactivated, THEN THE SYSTEM SHALL refuse login
  with `403`, and treat their existing sessions as anonymous.
- **AUTH-3.7** IF there have been 10 failed login attempts for the same email
  within 15 minutes, THEN THE SYSTEM SHALL respond `429` to further attempts
  for that email until the window passes.

### AUTH-4 Password reset

- **AUTH-4.1** WHEN anyone requests a password reset for an email, THE SYSTEM
  SHALL respond `202`, whether or not the account exists. IF an active account
  exists, THE SYSTEM SHALL email it a reset link.
- **AUTH-4.2** Reset tokens SHALL expire 1 hour after issue and be single-use.
- **AUTH-4.3** WHEN a valid reset token and a valid new password are submitted,
  THE SYSTEM SHALL update the password hash, mark the token used, mark the
  email verified, and revoke all of the user's sessions.
- **AUTH-4.4** IF the reset token is invalid, THEN THE SYSTEM SHALL respond `400`.

### AUTH-5 Magic link

- **AUTH-5.1** WHEN anyone requests a magic link for an email, THE SYSTEM SHALL
  respond `202`, whether or not the account exists. IF an active account
  exists, THE SYSTEM SHALL email it a login link.
- **AUTH-5.2** Magic-link tokens SHALL expire 15 minutes after issue and be
  single-use.
- **AUTH-5.3** WHEN a valid magic-link token is submitted, THE SYSTEM SHALL
  create a session (as in AUTH-3.1), mark the token used, and mark the email
  verified.
- **AUTH-5.4** IF the magic-link token is invalid, THEN THE SYSTEM SHALL respond `400`.

### AUTH-6 Account

- **AUTH-6.1** WHEN a logged-in user requests their account, THE SYSTEM SHALL
  return `id`, `email`, `email_verified`, and `created_at`.
- **AUTH-6.2** WHEN a logged-in user submits their current password and a valid
  new password, THE SYSTEM SHALL update the password and revoke all of their
  other sessions, keeping the current one. IF the current password is wrong,
  THE SYSTEM SHALL respond `400`.

### AUTH-7 Cross-cutting security

- **AUTH-7.1** Session and one-time tokens SHALL contain at least 32 bytes of
  randomness and be stored only as SHA-256 hashes.
- **AUTH-7.2** Issuing a new one-time token SHALL invalidate earlier unused
  tokens of the same purpose for that user.
- **AUTH-7.3** THE SYSTEM SHALL send email through a pluggable sender. The
  default development sender writes messages to the log.

## Out of scope

OAuth providers, 2FA, CAPTCHA, account deletion, and changing the email address
are not part of this spec. See "Later" in the product overview.
