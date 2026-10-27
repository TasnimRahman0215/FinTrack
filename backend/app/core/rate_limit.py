"""Small in-memory sliding-window rate limiter (enough for a single-process self-hosted app).

Used by app/api/v1/auth.py to slow down password guessing on login and signup. Counts live in
memory, so they reset when the server restarts and aren't shared between processes.
"""

import threading
import time
from collections import defaultdict, deque

from app.core.errors import TooManyRequests

# Every limiter registers itself here so tests can reset them all between cases.
_registry: list["RateLimiter"] = []


class RateLimiter:
    """Allows `max_hits` calls per `key` (e.g. client IP) within any `window_seconds` period."""

    def __init__(self, max_hits: int, window_seconds: int):
        self.max_hits = max_hits
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        _registry.append(self)

    def hit(self, key: str) -> None:
        """Record one attempt for `key`, or raise TooManyRequests if the limit is reached."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.max_hits:
                raise TooManyRequests("Too many attempts. Please wait a few minutes and try again.")
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def reset_all() -> None:
    """Clear every limiter. Used by the test suite (tests/conftest.py)."""
    for limiter in _registry:
        limiter.reset()
