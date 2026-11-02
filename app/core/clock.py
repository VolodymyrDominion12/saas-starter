from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    """Returns the current time as a timezone-aware UTC datetime."""

    def now(self) -> datetime:
        return datetime.now(UTC)
