from tests.conftest import register, token_from


async def _request(client, email="ann@example.com"):
    return await client.post("/api/auth/magic-link/request", json={"email": email})


async def test_request_sends_link_to_existing_account(client, mailer):
    """AUTH-5.1"""
    await register(client)
    response = await _request(client)
    assert response.status_code == 202
    assert "login link" in mailer.last_to("ann@example.com").subject


async def test_request_for_unknown_email_looks_the_same(client, mailer):
    """AUTH-5.1"""
    await register(client)
    known = await _request(client)
    count = len(mailer.outbox)
    unknown = await _request(client, "nobody@example.com")
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert len(mailer.outbox) == count


async def test_confirm_logs_in_and_verifies(client, new_client, mailer):
    """AUTH-5.3"""
    await register(client)
    browser = new_client()
    await _request(browser)
    token = token_from(mailer.last_to("ann@example.com"))

    response = await browser.post("/api/auth/magic-link/confirm", json={"token": token})
    assert response.status_code == 200
    assert response.json()["email_verified"] is True
    assert "httponly" in response.headers["set-cookie"].lower()
    assert (await browser.get("/api/auth/me")).status_code == 200


async def test_token_single_use(client, mailer):
    """AUTH-5.2"""
    await register(client)
    await _request(client)
    token = token_from(mailer.last_to("ann@example.com"))
    assert (
        await client.post("/api/auth/magic-link/confirm", json={"token": token})
    ).status_code == 200
    assert (
        await client.post("/api/auth/magic-link/confirm", json={"token": token})
    ).status_code == 400


async def test_token_expires_after_15_minutes(client, mailer, clock):
    """AUTH-5.2"""
    await register(client)
    await _request(client)
    token = token_from(mailer.last_to("ann@example.com"))
    clock.advance(minutes=15)
    assert (
        await client.post("/api/auth/magic-link/confirm", json={"token": token})
    ).status_code == 400


async def test_invalid_token_rejected(client):
    """AUTH-5.4"""
    response = await client.post("/api/auth/magic-link/confirm", json={"token": "bogus"})
    assert response.status_code == 400
