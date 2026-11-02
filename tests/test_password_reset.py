from sqlalchemy import select, update

from app.models import AuthToken, User
from tests.conftest import PASSWORD, register, token_from

NEW_PASSWORD = "a brand new password"


async def _request(client, email="ann@example.com"):
    return await client.post("/api/auth/password-reset/request", json={"email": email})


async def test_request_for_existing_account_sends_email(client, mailer):
    """AUTH-4.1"""
    await register(client)
    response = await _request(client, "ANN@example.com")
    assert response.status_code == 202
    assert mailer.last_to("ann@example.com").subject.startswith("Reset your")


async def test_request_for_unknown_email_looks_the_same(client, mailer):
    """AUTH-4.1"""
    await register(client)
    known = await _request(client)
    count = len(mailer.outbox)
    unknown = await _request(client, "nobody@example.com")

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert len(mailer.outbox) == count


async def test_request_for_inactive_account_sends_nothing(client, mailer, app):
    """AUTH-4.1"""
    await register(client)
    async with app.state.session_factory() as db:
        await db.execute(update(User).values(is_active=False))
        await db.commit()
    count = len(mailer.outbox)
    assert (await _request(client)).status_code == 202
    assert len(mailer.outbox) == count


async def test_confirm_changes_password_verifies_email_and_revokes_sessions(
    client, new_client, mailer
):
    """AUTH-4.3"""
    await register(client)
    other_browser = new_client()
    await other_browser.post(
        "/api/auth/login", json={"email": "ann@example.com", "password": PASSWORD}
    )
    await _request(client)
    token = token_from(mailer.last_to("ann@example.com"))

    response = await client.post(
        "/api/auth/password-reset/confirm", json={"token": token, "password": NEW_PASSWORD}
    )
    assert response.status_code == 204

    assert (await client.get("/api/auth/me")).status_code == 401
    assert (await other_browser.get("/api/auth/me")).status_code == 401

    fresh = new_client()
    old = await fresh.post(
        "/api/auth/login", json={"email": "ann@example.com", "password": PASSWORD}
    )
    assert old.status_code == 401
    new = await fresh.post(
        "/api/auth/login", json={"email": "ann@example.com", "password": NEW_PASSWORD}
    )
    assert new.status_code == 200
    assert new.json()["email_verified"] is True


async def test_token_is_single_use(client, mailer):
    """AUTH-4.2"""
    await register(client)
    await _request(client)
    token = token_from(mailer.last_to("ann@example.com"))
    body = {"token": token, "password": NEW_PASSWORD}

    assert (await client.post("/api/auth/password-reset/confirm", json=body)).status_code == 204
    assert (await client.post("/api/auth/password-reset/confirm", json=body)).status_code == 400


async def test_token_expires_after_1_hour(client, mailer, clock):
    """AUTH-4.2"""
    await register(client)
    await _request(client)
    token = token_from(mailer.last_to("ann@example.com"))
    clock.advance(hours=1)

    response = await client.post(
        "/api/auth/password-reset/confirm", json={"token": token, "password": NEW_PASSWORD}
    )
    assert response.status_code == 400


async def test_new_request_invalidates_old_token(client, mailer):
    """AUTH-7.2"""
    await register(client)
    await _request(client)
    first = token_from(mailer.last_to("ann@example.com"))
    await _request(client)

    response = await client.post(
        "/api/auth/password-reset/confirm", json={"token": first, "password": NEW_PASSWORD}
    )
    assert response.status_code == 400


async def test_invalid_token_rejected(client):
    """AUTH-4.4"""
    response = await client.post(
        "/api/auth/password-reset/confirm", json={"token": "bogus", "password": NEW_PASSWORD}
    )
    assert response.status_code == 400


async def test_weak_new_password_rejected(client, mailer):
    """AUTH-1.4 applies to reset"""
    await register(client)
    await _request(client)
    token = token_from(mailer.last_to("ann@example.com"))
    response = await client.post(
        "/api/auth/password-reset/confirm", json={"token": token, "password": "short"}
    )
    assert response.status_code == 422


async def test_tokens_stored_hashed(client, mailer, app):
    """AUTH-7.1"""
    await register(client)
    await _request(client)
    raw = token_from(mailer.last_to("ann@example.com"))
    async with app.state.session_factory() as db:
        hashes = (await db.scalars(select(AuthToken.token_hash))).all()
    assert raw not in hashes
    assert all(len(h) == 64 for h in hashes)
