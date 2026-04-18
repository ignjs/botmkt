"""Tests for utils/cache.py."""
import time
import pytest
from unittest.mock import patch

from utils.cache import PriceCache


def test_get_miss_returns_none():
    """Cache miss should return None."""
    cache = PriceCache(ttl_seconds=60)
    result = cache.get("AAPL")
    assert result is None


def test_set_and_get_returns_value_not_stale():
    """Fresh cache entry should be returned with is_stale=False."""
    cache = PriceCache(ttl_seconds=60)
    value = {"precio_actual": 150.0, "symbol": "AAPL"}
    cache.set("AAPL", value)

    result = cache.get("AAPL")
    assert result is not None
    cached_value, is_stale = result
    assert cached_value == value
    assert is_stale is False


def test_expired_entry_returns_stale_true():
    """Expired cache entry should be returned with is_stale=True."""
    cache = PriceCache(ttl_seconds=1)
    value = {"precio_actual": 200.0, "symbol": "MSFT"}
    cache.set("MSFT", value)

    # Simulate time passing beyond TTL
    with patch("time.monotonic", return_value=time.monotonic() + 10):
        result = cache.get("MSFT")

    assert result is not None
    cached_value, is_stale = result
    assert cached_value == value
    assert is_stale is True


def test_invalidate_removes_entry():
    """Invalidated key should no longer be found in cache."""
    cache = PriceCache(ttl_seconds=60)
    cache.set("GOOG", {"precio_actual": 2800.0})
    cache.invalidate("GOOG")

    result = cache.get("GOOG")
    assert result is None


def test_clear_all_removes_all():
    """clear_all should remove every entry from the cache."""
    cache = PriceCache(ttl_seconds=60)
    cache.set("AAPL", {"precio_actual": 150.0})
    cache.set("MSFT", {"precio_actual": 300.0})
    cache.set("GOOG", {"precio_actual": 2800.0})

    cache.clear_all()

    assert cache.get("AAPL") is None
    assert cache.get("MSFT") is None
    assert cache.get("GOOG") is None
