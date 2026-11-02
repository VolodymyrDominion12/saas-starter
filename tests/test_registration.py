import pytest
from sqlalchemy import select

from app.models import User
from tests.conftest import PASSWORD, register


async def test_register_creates_unverified_user_session_and_email(client, mailer):
    """AUTH-1.1"""
    response = await register(client, "ann@example.com")

    body = response.json()
    assert body["email"] == "ann@example.com"
    assert body["email_verified"] is False
    assert set(body) == {"id", "email", "email_verified", "created_at"}
    assert "session" in response.cookies
    assert mailer.last_to("ann@example.com").subject.startswith("Confirm your email")

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == body["id"]


async def test_email_is_normalised(client):
    """AUTH-1.2"""
    response = await register(client, "  Ann@Example.COM ")
    assert response.json()["email"] == "ann@example.com"


async def test_duplicate_email_conflicts_case_insensitively(client, app):
    """AUTH-1.3"""
    await register(client, "ann@example.com")
    response = await client.post(
        "/api/auth/register", json={"email": "ANN@example.com", "password": "another password"}
    )
    assert response.status_code == 409

    async with app.state.session_factory() as db:
        users = (await db.scalars(select(User))).all()
    assert len(users) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "not-an-email", "password": PASSWORD},
        {"email": "ann@example.com", "password": "short"},
        {"email": "ann@example.com", "password": "x" * 129},
        {"email": "ann@example.com"},
    ],
)
async def test_invalid_input_is_rejected(client, payload):
    """AUTH-1.4"""
    response = await client.post("/api/auth/register", json=payload)
    assert response.status_code == 422


async def test_password_stored_as_argon2id_hash(client, app):
    """AUTH-1.5"""
    await register(client, "ann@example.com")
    async with app.state.session_factory() as db:
        user = await db.scalar(select(User))
    assert user is not None
    assert user.password_hash is not None
    assert user.password_hash.startswith("$argon2id$")
    assert PASSWORD not in user.password_hash
