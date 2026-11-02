"""HTTP layer for spec 001. Translates requests to AuthService calls and errors to status codes."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.auth import service as svc
from app.auth.deps import (
    clear_session_cookie,
    client_info,
    current_session,
    current_user,
    get_app_settings,
    get_auth_service,
    session_token_from,
    set_session_cookie,
)
from app.auth.schemas import (
    ChangePasswordIn,
    EmailIn,
    LoginIn,
    PasswordResetConfirmIn,
    RegisterIn,
    TokenIn,
    UserOut,
)
from app.core.config import Settings
from app.models import User, UserSession

router = APIRouter(prefix="/api/auth", tags=["auth"])

INVALID_TOKEN = "This link is invalid or has expired"  # noqa: S105


def _http(error: svc.AuthError) -> HTTPException:
    mapping: dict[type[svc.AuthError], tuple[int, str]] = {
        svc.EmailAlreadyRegistered: (status.HTTP_409_CONFLICT, "Email is already registered"),
        svc.InvalidCredentials: (status.HTTP_401_UNAUTHORIZED, "Invalid email or password"),
        svc.AccountDisabled: (status.HTTP_403_FORBIDDEN, "Account is disabled"),
        svc.TooManyAttempts: (
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many failed attempts. Try again later",
        ),
        svc.InvalidToken: (status.HTTP_400_BAD_REQUEST, INVALID_TOKEN),
        svc.AlreadyVerified: (status.HTTP_400_BAD_REQUEST, "Email is already verified"),
        svc.WrongPassword: (status.HTTP_400_BAD_REQUEST, "Current password is incorrect"),
    }
    code, detail = mapping[type(error)]
    return HTTPException(code, detail)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterIn,
    request: Request,
    response: Response,
    service: svc.AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_app_settings),
) -> User:
    try:
        result = await service.register(body.email, body.password, client_info(request))
    except svc.AuthError as e:
        raise _http(e) from e
    set_session_cookie(response, settings, result.session_token)
    return result.user


@router.post("/login", response_model=UserOut)
async def login(
    body: LoginIn,
    request: Request,
    response: Response,
    service: svc.AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_app_settings),
) -> User:
    try:
        result = await service.login(body.email, body.password, client_info(request))
    except svc.AuthError as e:
        raise _http(e) from e
    set_session_cookie(response, settings, result.session_token)
    return result.user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    service: svc.AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_app_settings),
) -> Response:
    await service.logout(session_token_from(request))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookie(response, settings)
    return response


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)) -> User:
    return user


@router.post("/verify-email", response_model=UserOut)
async def verify_email(body: TokenIn, service: svc.AuthService = Depends(get_auth_service)) -> User:
    try:
        return await service.verify_email(body.token)
    except svc.AuthError as e:
        raise _http(e) from e


@router.post("/verify-email/resend", status_code=status.HTTP_202_ACCEPTED)
async def resend_verification(
    user: User = Depends(current_user),
    service: svc.AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    try:
        await service.resend_verification(user)
    except svc.AuthError as e:
        raise _http(e) from e
    return {"detail": "Verification email sent"}


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
async def request_password_reset(
    body: EmailIn, service: svc.AuthService = Depends(get_auth_service)
) -> dict[str, str]:
    await service.request_password_reset(body.email)
    return {"detail": "If an account exists for this email, we sent a reset link"}


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_password_reset(
    body: PasswordResetConfirmIn, service: svc.AuthService = Depends(get_auth_service)
) -> Response:
    try:
        await service.confirm_password_reset(body.token, body.password)
    except svc.AuthError as e:
        raise _http(e) from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/magic-link/request", status_code=status.HTTP_202_ACCEPTED)
async def request_magic_link(
    body: EmailIn, service: svc.AuthService = Depends(get_auth_service)
) -> dict[str, str]:
    await service.request_magic_link(body.email)
    return {"detail": "If an account exists for this email, we sent a login link"}


@router.post("/magic-link/confirm", response_model=UserOut)
async def confirm_magic_link(
    body: TokenIn,
    request: Request,
    response: Response,
    service: svc.AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_app_settings),
) -> User:
    try:
        result = await service.confirm_magic_link(body.token, client_info(request))
    except svc.AuthError as e:
        raise _http(e) from e
    set_session_cookie(response, settings, result.session_token)
    return result.user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordIn,
    session: UserSession = Depends(current_session),
    service: svc.AuthService = Depends(get_auth_service),
) -> Response:
    try:
        await service.change_password(session, body.current_password, body.new_password)
    except svc.AuthError as e:
        raise _http(e) from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)
