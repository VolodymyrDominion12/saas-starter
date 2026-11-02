"""Unit tests for pure helpers (no app, no database)."""

from app.core.ratelimit import SlidingWindowLimiter
from app.core.security import (
    generate_token,
    hash_password,
    hash_token,
    verify_password,
)


def test_password_hash_roundtrip():
    """AUTH-1.5"""
    hashed = hash_password("secret password")
    assert hashed.startswith("$argon2id$")
    assert verify_password(hashed, "secret password")
    assert not verify_password(hashed, "other password")


def test_verify_without_hash_is_false():
    """AUTH-3.2: missing users never authenticate."""
    assert verify_password(None, "anything") is False


def test_verify_with_garbage_hash_is_false():
    assert verify_password("not-a-hash", "anything") is False


def test_tokens_are_random_and_long():
    """AUTH-7.1"""
    tokens = {generate_token() for _ in range(100)}
    assert len(tokens) == 100
    assert all(len(t) >= 43 for t in tokens)


def test_token_hash_is_sha256_hex():
    """AUTH-7.1"""
    digest = hash_token("abc")
    assert digest == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_sliding_window_limiter():
    """AUTH-3.7"""
    now = [0.0]
    limiter = SlidingWindowLimiter(max_events=3, window_seconds=10, clock=lambda: now[0])
    for _ in range(3):
        assert not limiter.is_limited("k")
        limiter.hit("k")
    assert limiter.is_limited("k")
    assert not limiter.is_limited("other")

    now[0] = 10.0  # oldest events fall out of the window
    assert not limiter.is_limited("k")


def test_limiter_reset():
    limiter = SlidingWindowLimiter(max_events=1, window_seconds=10, clock=lambda: 0.0)
    limiter.hit("k")
    assert limiter.is_limited("k")
    limiter.reset("k")
    assert not limiter.is_limited("k")
