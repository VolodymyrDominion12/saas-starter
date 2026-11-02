from tests.conftest import PASSWORD, register

NEW_PASSWORD = "a brand new password"


async def test_me_returns_account_fields(client):
    """AUTH-6.1"""
    created = (await register(client)).json()
    response = await client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json() == created


async def test_me_requires_login(client):
    """AUTH-6.1, AUTH-3.5"""
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_change_password_keeps_current_session_revokes_others(client, new_client):
    """AUTH-6.2"""
    await register(client)
    other = new_client()
    await other.post("/api/auth/login", json={"email": "ann@example.com", "password": PASSWORD})

    response = await client.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 204
    assert (await client.get("/api/auth/me")).status_code == 200
    assert (await other.get("/api/auth/me")).status_code == 401

    login = await new_client().post(
        "/api/auth/login", json={"email": "ann@example.com", "password": NEW_PASSWORD}
    )
    assert login.status_code == 200


async def test_change_password_with_wrong_current_password(client):
    """AUTH-6.2"""
    await register(client)
    response = await client.post(
        "/api/auth/change-password",
        json={"current_password": "not it at all", "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 400


async def test_change_password_requires_login(client):
    """AUTH-6.2, AUTH-3.5"""
    response = await client.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 401


async def test_health(client):
    response = await client.get("/health")
    assert response.json() == {"status": "ok"}
