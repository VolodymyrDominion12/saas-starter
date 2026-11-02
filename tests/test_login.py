from sqlalchemy import select, update

from app.models import User, UserSession
from tests.conftest import PASSWORD, register


async def _login(client, email="ann@example.com", password=PASSWORD):
    return await client.post("/api/auth/login", json={"email": email, "password": password})


async def test_login_sets_secure_session_cookie(client, new_client):
    """AUTH-3.1"""
    await register(client)
    browser = new_client()

    response = await _login(browser, "ANN@example.com")
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "session=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "path=/" in cookie
    assert "secure" not in cookie  # COOKIE_SECURE is off in tests
    assert (await browser.get("/api/auth/me")).status_code == 200


async def test_cookie_marked_secure_when_enabled(app, client):
    """AUTH-3.1"""
    app.state.settings = app.state.settings.model_copy(update={"cookie_secure": True})
    response = await client.post(
        "/api/auth/register", json={"email": "ann@example.com", "password": PASSWORD}
    )
    assert "secure" in response.headers["set-cookie"].lower()


async def test_wrong_password_and_unknown_email_look_the_same(client, new_client):
    """AUTH-3.2"""
    await register(client)
    wrong = await _login(new_client(), password="wrong password")
    unknown = await _login(new_client(), email="nobody@example.com")

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


async def test_session_expires_after_30_days(client, clock):
    """AUTH-3.3, AUTH-3.5"""
    await register(client)
    clock.advance(days=29, hours=23)
    assert (await client.get("/api/auth/me")).status_code == 200
    clock.advance(hours=1)
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_logout_deletes_session_and_clears_cookie(client, app):
    """AUTH-3.4"""
    await register(client)
    response = await client.post("/api/auth/logout")
    assert response.status_code == 204
    assert 'session=""' in response.headers["set-cookie"] or "max-age=0" in (
        response.headers["set-cookie"].lower()
    )
    assert (await client.get("/api/auth/me")).status_code == 401

    async with app.state.session_factory() as db:
        assert (await db.scalars(select(UserSession))).all() == []


async def test_logout_when_anonymous_is_harmless(client):
    """AUTH-3.4"""
    assert (await client.post("/api/auth/logout")).status_code == 204


async def test_unknown_session_cookie_is_anonymous(client):
    """AUTH-3.5"""
    client.cookies.set("session", "forged-token")
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_deactivated_user_cannot_login_and_sessions_stop_working(client, new_client, app):
    """AUTH-3.6"""
    await register(client)
    async with app.state.session_factory() as db:
        await db.execute(update(User).values(is_active=False))
        await db.commit()

    assert (await client.get("/api/auth/me")).status_code == 401
    assert (await _login(new_client())).status_code == 403


async def test_login_rate_limited_after_10_failures(client, new_client, clock):
    """AUTH-3.7"""
    await register(client)
    browser = new_client()
    for _ in range(10):
        assert (await _login(browser, password="wrong password")).status_code == 401

    # Even the correct password is refused while limited.
    assert (await _login(browser)).status_code == 429
    assert (await _login(browser, email="Ann@Example.com")).status_code == 429

    clock.advance(minutes=15, seconds=1)
    assert (await _login(browser)).status_code == 200


async def test_rate_limit_is_per_email(client, new_client):
    """AUTH-3.7"""
    await register(client, "ann@example.com")
    await register(new_client(), "bob@example.com")
    browser = new_client()
    for _ in range(10):
        await _login(browser, password="wrong password")

    assert (await _login(browser, email="bob@example.com")).status_code == 200


async def test_session_stores_only_token_hash(client, app):
    """AUTH-7.1"""
    response = await register(client)
    raw = response.cookies["session"]
    async with app.state.session_factory() as db:
        session = await db.scalar(select(UserSession))
    assert session is not None
    assert session.token_hash != raw
    assert len(session.token_hash) == 64
    assert len(raw) >= 43  # 32 bytes, base64url
