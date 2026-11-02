from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import AuthService, ClientInfo
from app.core.config import Settings
from app.core.db import get_db
from app.models import User, UserSession


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_auth_service(request: Request, db: AsyncSession = Depends(get_db)) -> AuthService:
    state = request.app.state
    return AuthService(
        db=db,
        settings=state.settings,
        mailer=state.mailer,
        clock=state.clock,
        login_limiter=state.login_limiter,
    )


def client_info(request: Request) -> ClientInfo:
    return ClientInfo(
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )


def session_token_from(request: Request) -> str | None:
    return request.cookies.get(request.app.state.settings.session_cookie_name)


async def optional_session(
    request: Request, service: AuthService = Depends(get_auth_service)
) -> UserSession | None:
    return await service.resolve_session(session_token_from(request))


async def current_session(
    session: UserSession | None = Depends(optional_session),
) -> UserSession:
    """AUTH-3.5: protected endpoints answer 401 for anonymous requests."""
    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return session


async def current_user(session: UserSession = Depends(current_session)) -> User:
    return session.user


def set_session_cookie(response: Response, settings: Settings, token: str) -> None:
    """AUTH-3.1."""
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_days * 24 * 3600,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
