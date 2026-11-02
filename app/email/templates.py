"""Plain-text auth emails. HTML templates come with the web UI (spec 005)."""

from urllib.parse import urlencode

from app.core.config import Settings
from app.email.sender import EmailMessage


def _link(settings: Settings, path: str, token: str) -> str:
    return f"{settings.base_url}{path}?{urlencode({'token': token})}"


def verify_email(settings: Settings, to: str, token: str, ttl_minutes: int) -> EmailMessage:
    link = _link(settings, "/auth/verify-email", token)
    hours = ttl_minutes // 60
    return EmailMessage(
        to=to,
        subject=f"Confirm your email for {settings.app_name}",
        text=(
            f"Welcome to {settings.app_name}!\n\n"
            f"Confirm your email address by opening this link:\n{link}\n\n"
            f"The link expires in {hours} hours. If you did not sign up, ignore this email."
        ),
    )


def password_reset(settings: Settings, to: str, token: str, ttl_minutes: int) -> EmailMessage:
    link = _link(settings, "/auth/reset-password", token)
    return EmailMessage(
        to=to,
        subject=f"Reset your {settings.app_name} password",
        text=(
            f"Someone asked to reset the password for your {settings.app_name} account.\n\n"
            f"Choose a new password here:\n{link}\n\n"
            f"The link expires in {ttl_minutes} minutes and works once. "
            "If it was not you, ignore this email; your password stays the same."
        ),
    )


def magic_link(settings: Settings, to: str, token: str, ttl_minutes: int) -> EmailMessage:
    link = _link(settings, "/auth/magic-link", token)
    return EmailMessage(
        to=to,
        subject=f"Your {settings.app_name} login link",
        text=(
            f"Log in to {settings.app_name} with this link:\n{link}\n\n"
            f"The link expires in {ttl_minutes} minutes and works once. "
            "If you did not request it, ignore this email."
        ),
    )
