import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.auth.router import router as auth_router
from app.core.clock import Clock, SystemClock
from app.core.config import Settings, get_settings
from app.core.db import create_engine, create_session_factory
from app.core.ratelimit import SlidingWindowLimiter
from app.email.sender import ConsoleEmailSender, EmailSender


def create_app(
    settings: Settings | None = None,
    mailer: EmailSender | None = None,
    clock: Clock | None = None,
) -> FastAPI:
    """Application factory. Tests pass their own settings, mailer and clock."""
    settings = settings or get_settings()
    logging.basicConfig(level=logging.INFO)

    engine = create_engine(settings.database_url, echo=settings.database_echo)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        await engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.mailer = mailer or ConsoleEmailSender()
    app_clock = clock or SystemClock()
    app.state.clock = app_clock
    app.state.login_limiter = SlidingWindowLimiter(
        settings.login_max_failures,
        settings.login_window_seconds,
        clock=lambda: app_clock.now().timestamp(),
    )

    app.include_router(auth_router)

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
