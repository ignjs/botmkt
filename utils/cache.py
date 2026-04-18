"""In-memory price cache with TTL-based expiration."""
import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PriceCache:
    """Thread-safe in-memory cache for price data with TTL expiration.

    Args:
        ttl_seconds: Time-to-live in seconds for cached entries (default 60).
    """

    def __init__(self, ttl_seconds: int = 60) -> None:
        """Initialise the cache.

        Args:
            ttl_seconds: Seconds before a cache entry is considered expired.
        """
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[Any, float, bool]] = {}  # key -> (value, expires_at, stale)
        self._logger = logging.getLogger(__name__)

    def get(self, key: str) -> Optional[tuple[Any, bool]]:
        """Retrieve a cached value by key.

        Args:
            key: Cache key (typically a ticker symbol).

        Returns:
            Optional[tuple[Any, bool]]: Tuple of (value, is_stale) if found, or None if not cached.

        Raises:
            None
        """
        try:
            if key not in self._store:
                return None
            value, expires_at, _ = self._store[key]
            is_stale = time.monotonic() > expires_at
            return value, is_stale
        except Exception as e:
            self._logger.exception("Error en cache.get(%s): %s", key, e)
            return None

    def set(self, key: str, value: Any) -> None:
        """Store a value in the cache with a fresh TTL.

        Args:
            key: Cache key.
            value: Data to cache.

        Returns:
            None
        """
        try:
            expires_at = time.monotonic() + self._ttl
            self._store[key] = (value, expires_at, False)
        except Exception as e:
            self._logger.exception("Error en cache.set(%s): %s", key, e)

    def invalidate(self, key: str) -> None:
        """Remove a specific key from the cache.

        Args:
            key: Cache key to remove.

        Returns:
            None
        """
        try:
            self._store.pop(key, None)
        except Exception as e:
            self._logger.exception("Error en cache.invalidate(%s): %s", key, e)

    def clear_all(self) -> None:
        """Remove all entries from the cache.

        Returns:
            None
        """
        try:
            self._store.clear()
        except Exception as e:
            self._logger.exception("Error en cache.clear_all: %s", e)


# Global instance
price_cache = PriceCache(ttl_seconds=60)
"""Global price cache with 60-second TTL."""
