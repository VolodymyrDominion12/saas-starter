"""Authentication business rules (spec 001). No HTTP concerns live here."""

import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value

from app.core.clock import Clock
from app.core.config import Settings
from app.core.ratelimit import SlidingWindowLimiter
from app.core.security import (
    generate_token,
    hash_password,
    hash_token,
    password_needs_rehash,
    verify_password,
)
from app.email import templates
from app.email.sender import EmailSender
from app.models import AuthToken, TokenPurpose, User, UserSession

LAST_SEEN_RESOLUTION = timedelta(minutes=5)


class AuthError(Exception):
    """Base class for expected authentication failures."""


class EmailAlreadyRegistered(AuthError):
    pass


class InvalidCredentials(AuthError):
    pass


class AccountDisabled(AuthError):
    pass


class TooManyAttempts(AuthError):
    pass


class InvalidToken(AuthError):
    pass


class AlreadyVerified(AuthError):
    pass


class WrongPassword(AuthError):
    pass


@dataclass(frozen=True, slots=True)
class ClientInfo:
    user_agent: str | None = None
    ip_address: str | None = None


@dataclass(frozen=True, slots=True)
class LoginResult:
    user: User
    session_token: str


def normalize_email(email: str) -> str:
    """AUTH-1.2: trim and lowercase."""
    return email.strip().lower()


class AuthService:
    def __init__(
        self,
        db: AsyncSession,
        settings: Settings,
        mailer: EmailSender,
        clock: Clock,
        login_limiter: SlidingWindowLimiter,
    ) -> None:
        self.db = db
        self.settings = settings
        self.mailer = mailer
        self.clock = clock
        self.login_limiter = login_limiter

    # ---- registration & verification -------------------------------------------------

    async def register(self, email: str, password: str, client: ClientInfo) -> LoginResult:
        """AUTH-1.1 to 1.5."""
        email = normalize_email(email)
        if await self._get_user_by_email(email) is not None:
            raise EmailAlreadyRegistered

        now = self.clock.now()
        user = User(
            email=email, password_hash=hash_password(password), created_at=now, updated_at=now
        )
        self.db.add(user)
        try:
            await self.db.flush()
        except IntegrityError as exc:  # a concurrent signup won the race
            await self.db.rollback()
            raise EmailAlreadyRegistered from exc

        verify_token = await self._issue_token(user, TokenPurpose.VERIFY_EMAIL)
        session_token = await self._create_session(user, client)
        await self.db.commit()

        await self._send_verification(user, verify_token)
        return LoginResult(user=user, session_token=session_token)

    async def verify_email(self, raw_token: str) -> User:
        """AUTH-2.1, 2.2."""
        token = await self._consume_token(raw_token, TokenPurpose.VERIFY_EMAIL)
        self._mark_verified(token.user)
        await self.db.commit()
        return token.user

    async def resend_verification(self, user: User) -> None:
        """AUTH-2.4."""
        if user.email_verified:
            raise AlreadyVerified
        raw = await self._issue_token(user, TokenPurpose.VERIFY_EMAIL)
        await self.db.commit()
        await self._send_verification(user, raw)

    # ---- login, sessions -----------------------------------------------------------------

    async def login(self, email: str, password: str, client: ClientInfo) -> LoginResult:
        """AUTH-3.1, 3.2, 3.6, 3.7."""
        email = normalize_email(email)
        if self.login_limiter.is_limited(email):
            raise TooManyAttempts

        user = await self._get_user_by_email(email)
        # verify_password runs a dummy hash when user is None (timing-safe miss).
        if not verify_password(user.password_hash if user else None, password) or user is None:
            self.login_limiter.hit(email)
            raise InvalidCredentials
        if not user.is_active:
            raise AccountDisabled

        self.login_limiter.reset(email)
        assert user.password_hash is not None  # noqa: S101 - guaranteed by verify_password
        if password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
        session_token = await self._create_session(user, client)
        await self.db.commit()
        return LoginResult(user=user, session_token=session_token)

    async def resolve_session(self, raw_token: str | None) -> UserSession | None:
        """AUTH-3.5, 3.6: return the live session for a cookie value, else None."""
        if not raw_token:
            return None
        session = await self.db.scalar(
            select(UserSession).where(UserSession.token_hash == hash_token(raw_token))
        )
        now = self.clock.now()
        if session is None or session.expires_at <= now or not session.user.is_active:
            return None
        if now - session.last_seen_at >= LAST_SEEN_RESOLUTION:
            session.last_seen_at = now
            await self.db.commit()
        return session

    async def logout(self, raw_token: str | None) -> None:
        """AUTH-3.4."""
        if not raw_token:
            return
        await self.db.execute(
            delete(UserSession).where(UserSession.token_hash == hash_token(raw_token))
        )
        await self.db.commit()

    async def revoke_sessions(
        self, user_id: uuid.UUID, keep_session_id: uuid.UUID | None = None
    ) -> None:
        stmt = delete(UserSession).where(UserSession.user_id == user_id)
        if keep_session_id is not None:
            stmt = stmt.where(UserSession.id != keep_session_id)
        await self.db.execute(stmt)

    # ---- password reset --------------------------------------------------------------------

    async def request_password_reset(self, email: str) -> None:
        """AUTH-4.1: silent for unknown or inactive accounts."""
        user = await self._get_user_by_email(normalize_email(email))
        if user is None or not user.is_active:
            return
        raw = await self._issue_token(user, TokenPurpose.PASSWORD_RESET)
        await self.db.commit()
        await self.mailer.send(
            templates.password_reset(
                self.settings, user.email, raw, self.settings.password_reset_ttl_minutes
            )
        )

    async def confirm_password_reset(self, raw_token: str, new_password: str) -> None:
        """AUTH-4.2 to 4.4."""
        token = await self._consume_token(raw_token, TokenPurpose.PASSWORD_RESET)
        user = token.user
        user.password_hash = hash_password(new_password)
        self._mark_verified(user)
        await self.revoke_sessions(user.id)
        await self.db.commit()

    # ---- magic link ------------------------------------------------------------------------

    async def request_magic_link(self, email: str) -> None:
        """AUTH-5.1: silent for unknown or inactive accounts."""
        user = await self._get_user_by_email(normalize_email(email))
        if user is None or not user.is_active:
            return
        raw = await self._issue_token(user, TokenPurpose.MAGIC_LINK)
        await self.db.commit()
        await self.mailer.send(
            templates.magic_link(
                self.settings, user.email, raw, self.settings.magic_link_ttl_minutes
            )
        )

    async def confirm_magic_link(self, raw_token: str, client: ClientInfo) -> LoginResult:
        """AUTH-5.2 to 5.4."""
        token = await self._consume_token(raw_token, TokenPurpose.MAGIC_LINK)
        user = token.user
        self._mark_verified(user)
        session_token = await self._create_session(user, client)
        await self.db.commit()
        return LoginResult(user=user, session_token=session_token)

    # ---- account ---------------------------------------------------------------------------

    async def change_password(
        self, session: UserSession, current_password: str, new_password: str
    ) -> None:
        """AUTH-6.2: keeps the current session, revokes the others."""
        user = session.user
        if not verify_password(user.password_hash, current_password):
            raise WrongPassword
        user.password_hash = hash_password(new_password)
        await self.revoke_sessions(user.id, keep_session_id=session.id)
        await self.db.commit()

    # ---- internals -------------------------------------------------------------------------

    async def _get_user_by_email(self, email: str) -> User | None:
        return await self.db.scalar(select(User).where(User.email == email))

    def _mark_verified(self, user: User) -> None:
        if user.email_verified_at is None:
            user.email_verified_at = self.clock.now()

    def _token_ttl(self, purpose: TokenPurpose) -> timedelta:
        minutes = {
            TokenPurpose.VERIFY_EMAIL: self.settings.verify_email_ttl_minutes,
            TokenPurpose.PASSWORD_RESET: self.settings.password_reset_ttl_minutes,
            TokenPurpose.MAGIC_LINK: self.settings.magic_link_ttl_minutes,
        }[purpose]
        return timedelta(minutes=minutes)

    async def _issue_token(self, user: User, purpose: TokenPurpose) -> str:
        """AUTH-7.1, 7.2: invalidate earlier unused tokens, store only the hash."""
        now = self.clock.now()
        await self.db.execute(
            update(AuthToken)
            .where(
                AuthToken.user_id == user.id,
                AuthToken.purpose == purpose.value,
                AuthToken.used_at.is_(None),
            )
            .values(used_at=now)
        )
        raw = generate_token()
        self.db.add(
            AuthToken(
                user_id=user.id,
                purpose=purpose.value,
                token_hash=hash_token(raw),
                created_at=now,
                expires_at=now + self._token_ttl(purpose),
            )
        )
        await self.db.flush()
        return raw

    async def _consume_token(self, raw_token: str, purpose: TokenPurpose) -> AuthToken:
        """Mark a token used, or raise InvalidToken. Safe against double use."""
        now = self.clock.now()
        token = await self.db.scalar(
            select(AuthToken).where(AuthToken.token_hash == hash_token(raw_token))
        )
        if (
            token is None
            or token.purpose != purpose.value
            or token.used_at is not None
            or token.expires_at <= now
            or not token.user.is_active
        ):
            raise InvalidToken
        result = await self.db.execute(
            update(AuthToken)
            .where(AuthToken.id == token.id, AuthToken.used_at.is_(None))
            .values(used_at=now)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:  # consumed concurrently by another request
            await self.db.rollback()
            raise InvalidToken
        set_committed_value(token, "used_at", now)
        return token

    async def _create_session(self, user: User, client: ClientInfo) -> str:
        now = self.clock.now()
        raw = generate_token()
        self.db.add(
            UserSession(
                user_id=user.id,
                token_hash=hash_token(raw),
                created_at=now,
                last_seen_at=now,
                expires_at=now + timedelta(days=self.settings.session_ttl_days),
                user_agent=(client.user_agent or "")[:512] or None,
                ip_address=client.ip_address,
            )
        )
        await self.db.flush()
        return raw

    async def _send_verification(self, user: User, raw: str) -> None:
        await self.mailer.send(
            templates.verify_email(
                self.settings, user.email, raw, self.settings.verify_email_ttl_minutes
            )
        )
