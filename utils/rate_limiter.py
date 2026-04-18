"""Token-bucket style in-memory rate limiter for per-user request throttling."""

import logging
import time
from collections import defaultdict, deque


class RateLimiter:
    """Sliding-window rate limiter that tracks calls per user.

    Uses a deque of timestamps to count how many calls a given user has made
    within the rolling ``window_seconds`` window.

    Args:
        max_calls: Maximum number of allowed calls per window.
        window_seconds: Duration of the sliding window in seconds.
    """

    def __init__(self, max_calls: int, window_seconds: int) -> None:
        """Initialise the rate limiter.

        Args:
            max_calls: Maximum allowed calls within the window.
            window_seconds: Size of the sliding time window in seconds.
        """
        self._max_calls = max_calls
        self._window_seconds = window_seconds
        self._calls: dict[int, deque] = defaultdict(deque)
        self._logger = logging.getLogger(__name__)

    def is_allowed(self, user_id: int) -> tuple[bool, int]:
        """Check whether a user is allowed to make a new call.

        Cleans up timestamps older than the window before deciding.

        Args:
            user_id: Numeric Telegram user identifier.

        Returns:
            tuple[bool, int]: A tuple of (allowed, retry_after_seconds).
                ``allowed`` is True when the call should proceed.
                ``retry_after_seconds`` is 0 when allowed, or the number of
                seconds the caller should wait before retrying.

        Raises:
            Exception: Propagates unexpected errors after logging.
        """
        try:
            now = time.monotonic()
            window_start = now - self._window_seconds
            timestamps = self._calls[user_id]

            # Evict calls outside the current window
            while timestamps and timestamps[0] <= window_start:
                timestamps.popleft()

            if len(timestamps) >= self._max_calls:
                oldest = timestamps[0]
                retry_after = int(oldest - window_start) + 1
                self._logger.debug(
                    "Rate limit exceeded for user %s — retry in %ss", user_id, retry_after
                )
                return False, retry_after

            timestamps.append(now)
            return True, 0
        except Exception as e:
            self._logger.exception("Error en is_allowed para user %s: %s", user_id, e)
            raise


# ---------------------------------------------------------------------------
# Global instances
# ---------------------------------------------------------------------------

ai_limiter = RateLimiter(max_calls=3, window_seconds=60)
"""Rate limiter for AI-powered endpoints: 3 calls per 60 seconds per user."""

data_limiter = RateLimiter(max_calls=10, window_seconds=30)
"""Rate limiter for market-data endpoints: 10 calls per 30 seconds per user."""
