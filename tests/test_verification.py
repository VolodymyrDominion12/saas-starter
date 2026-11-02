from tests.conftest import register, token_from


async def test_valid_token_verifies_email_once(client, mailer):
    """AUTH-2.1, AUTH-2.2 (reuse)"""
    await register(client)
    token = token_from(mailer.last_to("ann@example.com"))

    response = await client.post("/api/auth/verify-email", json={"token": token})
    assert response.status_code == 200
    assert response.json()["email_verified"] is True

    again = await client.post("/api/auth/verify-email", json={"token": token})
    assert again.status_code == 400


async def test_unknown_token_rejected(client):
    """AUTH-2.2"""
    response = await client.post("/api/auth/verify-email", json={"token": "nope"})
    assert response.status_code == 400


async def test_token_of_other_purpose_rejected(client, mailer):
    """AUTH-2.2"""
    await register(client)
    await client.post("/api/auth/password-reset/request", json={"email": "ann@example.com"})
    reset_token = token_from(mailer.last_to("ann@example.com"))

    response = await client.post("/api/auth/verify-email", json={"token": reset_token})
    assert response.status_code == 400
    me = await client.get("/api/auth/me")
    assert me.json()["email_verified"] is False


async def test_token_expires_after_24_hours(client, mailer, clock):
    """AUTH-2.3"""
    await register(client)
    token = token_from(mailer.last_to("ann@example.com"))
    clock.advance(hours=24, seconds=1)

    response = await client.post("/api/auth/verify-email", json={"token": token})
    assert response.status_code == 400


async def test_token_valid_just_before_expiry(client, mailer, clock):
    """AUTH-2.3"""
    await register(client)
    token = token_from(mailer.last_to("ann@example.com"))
    clock.advance(hours=23, minutes=59)

    response = await client.post("/api/auth/verify-email", json={"token": token})
    assert response.status_code == 200


async def test_resend_invalidates_previous_token(client, mailer):
    """AUTH-2.4, AUTH-7.2"""
    await register(client)
    first = token_from(mailer.last_to("ann@example.com"))

    response = await client.post("/api/auth/verify-email/resend")
    assert response.status_code == 202
    second = token_from(mailer.last_to("ann@example.com"))
    assert first != second

    assert (await client.post("/api/auth/verify-email", json={"token": first})).status_code == 400
    assert (await client.post("/api/auth/verify-email", json={"token": second})).status_code == 200


async def test_resend_when_verified_is_rejected(client, mailer):
    """AUTH-2.4"""
    await register(client)
    await client.post(
        "/api/auth/verify-email", json={"token": token_from(mailer.last_to("ann@example.com"))}
    )
    response = await client.post("/api/auth/verify-email/resend")
    assert response.status_code == 400


async def test_resend_requires_login(client):
    """AUTH-2.4, AUTH-3.5"""
    response = await client.post("/api/auth/verify-email/resend")
    assert response.status_code == 401
