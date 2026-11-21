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
        self._last_sweep = time.monotonic()
        _registry.append(self)

    def hit(self, key: str) -> None:
        """Record one attempt for `key`, or raise TooManyRequests if the limit is reached."""
        now = time.monotonic()
        with self._lock:
            self._sweep(now)
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.max_hits:
                raise TooManyRequests("Too many attempts. Please wait a few minutes and try again.")
            hits.append(now)

    def _sweep(self, now: float) -> None:
        """Forget keys with no hits inside the window, so the dict can't grow without bound
        (every new IP or email would otherwise stay in memory until a restart)."""
        if now - self._last_sweep < self.window:
            return
        self._last_sweep = now
        for key in [
            k for k, hits in self._hits.items() if not hits or now - hits[-1] > self.window
        ]:
            del self._hits[key]

    def __len__(self) -> int:
        return len(self._hits)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def reset_all() -> None:
    """Clear every limiter. Used by the test suite (tests/conftest.py)."""
    for limiter in _registry:
        limiter.reset()
