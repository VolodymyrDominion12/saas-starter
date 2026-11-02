import re
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from app.core.config import Settings
from app.email.sender import EmailMessage, MemoryEmailSender
from app.main import create_app
from app.models import Base

PASSWORD = "correct horse battery"


class FakeClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current

    def advance(self, **kwargs: float) -> None:
        self.current += timedelta(**kwargs)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def mailer() -> MemoryEmailSender:
    return MemoryEmailSender()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        app_url="http://testserver",
    )


@pytest.fixture
async def app(
    settings: Settings, mailer: MemoryEmailSender, clock: FakeClock
) -> AsyncIterator[FastAPI]:
    application = create_app(settings=settings, mailer=mailer, clock=clock)
    async with application.state.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield application
    await application.state.engine.dispose()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.fixture
async def new_client(app: FastAPI) -> AsyncIterator[Callable[[], httpx.AsyncClient]]:
    """Factory for extra clients: a second browser with its own cookie jar."""
    clients: list[httpx.AsyncClient] = []

    def make() -> httpx.AsyncClient:
        c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")
        clients.append(c)
        return c

    yield make
    for c in clients:
        await c.aclose()


def token_from(message: EmailMessage) -> str:
    match = re.search(r"token=([\w\-]+)", message.text)
    assert match, f"no token in email: {message.text}"
    return match.group(1)


async def register(
    client: httpx.AsyncClient, email: str = "ann@example.com", password: str = PASSWORD
) -> httpx.Response:
    response = await client.post("/api/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    return response
