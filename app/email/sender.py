"""Pluggable email delivery (AUTH-7.3). Resend/SMTP senders arrive with spec 004."""

import logging
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger("app.email")


@dataclass(frozen=True, slots=True)
class EmailMessage:
    to: str
    subject: str
    text: str
    html: str | None = None


class EmailSender(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


class ConsoleEmailSender:
    """Development sender: writes the message to the log instead of sending it."""

    async def send(self, message: EmailMessage) -> None:
        logger.info("Email to %s\nSubject: %s\n\n%s", message.to, message.subject, message.text)


class MemoryEmailSender:
    """Test sender: keeps messages in a list."""

    def __init__(self) -> None:
        self.outbox: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.outbox.append(message)

    def last_to(self, email: str) -> EmailMessage:
        for message in reversed(self.outbox):
            if message.to == email:
                return message
        raise LookupError(f"No email sent to {email}")
