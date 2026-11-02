"""Password hashing and opaque token helpers (AUTH-1.5, AUTH-7.1)."""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()  # Argon2id with library defaults

TOKEN_BYTES = 32

# Used when the user does not exist, so a failed login takes about as long
# as a wrong password and does not reveal which emails are registered.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Check a password. Runs a dummy verification when there is no hash."""
    try:
        _hasher.verify(password_hash or _DUMMY_HASH, password)
    except (VerificationError, InvalidHashError):
        return False
    return password_hash is not None


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def generate_token() -> str:
    """A URL-safe random token with 32 bytes of entropy."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    """SHA-256 hex digest. Tokens are high-entropy, so a fast hash is sufficient."""
    return hashlib.sha256(token.encode()).hexdigest()
