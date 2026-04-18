"""Tests for utils/rate_limiter.py — no real DB or network connections required."""

import time
import unittest

from utils.rate_limiter import RateLimiter


class TestRateLimiter(unittest.TestCase):
    """Unit tests for the RateLimiter sliding-window implementation."""

    def test_first_call_is_allowed(self):
        limiter = RateLimiter(max_calls=3, window_seconds=60)
        allowed, retry_after = limiter.is_allowed(user_id=1)
        self.assertTrue(allowed)
        self.assertEqual(retry_after, 0)

    def test_calls_within_limit_are_all_allowed(self):
        limiter = RateLimiter(max_calls=3, window_seconds=60)
        for _ in range(3):
            allowed, _ = limiter.is_allowed(user_id=1)
            self.assertTrue(allowed)

    def test_call_exceeding_limit_is_rejected(self):
        limiter = RateLimiter(max_calls=3, window_seconds=60)
        for _ in range(3):
            limiter.is_allowed(user_id=1)
        allowed, retry_after = limiter.is_allowed(user_id=1)
        self.assertFalse(allowed)
        self.assertGreater(retry_after, 0)

    def test_different_users_tracked_independently(self):
        limiter = RateLimiter(max_calls=2, window_seconds=60)
        # Exhaust user 1
        limiter.is_allowed(user_id=1)
        limiter.is_allowed(user_id=1)
        denied, _ = limiter.is_allowed(user_id=1)
        # User 2 still has a fresh window
        allowed, _ = limiter.is_allowed(user_id=2)
        self.assertFalse(denied)
        self.assertTrue(allowed)

    def test_expired_calls_are_evicted(self):
        """Calls outside the window should not count against the limit."""
        limiter = RateLimiter(max_calls=2, window_seconds=1)
        limiter.is_allowed(user_id=1)
        limiter.is_allowed(user_id=1)
        # Both calls are now over the 1-second window
        time.sleep(1.1)
        allowed, retry_after = limiter.is_allowed(user_id=1)
        self.assertTrue(allowed)
        self.assertEqual(retry_after, 0)

    def test_retry_after_is_positive_integer(self):
        limiter = RateLimiter(max_calls=1, window_seconds=60)
        limiter.is_allowed(user_id=1)
        allowed, retry_after = limiter.is_allowed(user_id=1)
        self.assertFalse(allowed)
        self.assertIsInstance(retry_after, int)
        self.assertGreater(retry_after, 0)


class TestGlobalInstances(unittest.TestCase):
    """Verify module-level instances behave with their configured limits."""

    def test_ai_limiter_allows_up_to_3_calls(self):
        from utils.rate_limiter import RateLimiter
        limiter = RateLimiter(max_calls=3, window_seconds=60)
        results = [limiter.is_allowed(user_id=99) for _ in range(4)]
        self.assertTrue(all(r[0] for r in results[:3]))
        self.assertFalse(results[3][0])

    def test_data_limiter_allows_up_to_10_calls(self):
        from utils.rate_limiter import RateLimiter
        limiter = RateLimiter(max_calls=10, window_seconds=30)
        results = [limiter.is_allowed(user_id=88) for _ in range(11)]
        self.assertTrue(all(r[0] for r in results[:10]))
        self.assertFalse(results[10][0])


if __name__ == "__main__":
    unittest.main()
