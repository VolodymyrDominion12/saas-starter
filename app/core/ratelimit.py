"""In-process sliding-window limiter used for failed logins (AUTH-3.7).

It keeps state per process. With several workers each one counts separately,
so the effective limit is multiplied; a Redis-backed limiter is planned.
"""

import time
from collections import defaultdict, deque
from collections.abc import Callable


class SlidingWindowLimiter:
    def __init__(
        self,
        max_events: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._clock = clock
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str) -> deque[float]:
        events = self._events[key]
        cutoff = self._clock() - self.window_seconds
        while events and events[0] <= cutoff:
            events.popleft()
        if not events:
            self._events.pop(key, None)
            return deque()
        return events

    def is_limited(self, key: str) -> bool:
        return len(self._prune(key)) >= self.max_events

    def hit(self, key: str) -> None:
        self._prune(key)
        self._events[key].append(self._clock())

    def reset(self, key: str) -> None:
        self._events.pop(key, None)
