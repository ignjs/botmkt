"""Unit tests for services/recommendation_tracker.py — E4."""
from datetime import datetime, timezone, timedelta

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _pending_rec(symbol: str, recommendation: str, price_entry: float, days_ago: int) -> dict:
    recommended_at = datetime.now(timezone.utc) - timedelta(days=days_ago + 1)
    return {
        "id": 1,
        "symbol": symbol,
        "recommendation": recommendation,
        "price_at_recommendation": price_entry,
        "recommended_at": recommended_at,
        "price_5d": None,
        "price_10d": None,
        "price_20d": None,
        "result_5d": "pendiente",
        "result_10d": "pendiente",
        "result_20d": "pendiente",
    }


def test_evaluate_buy_correct():
    """A 'comprar' recommendation is correct if price rose > 2%."""
    from services.recommendation_tracker import _evaluate_recommendation

    assert _evaluate_recommendation("comprar", 100.0, 103.0) == "acierto"
    assert _evaluate_recommendation("comprar", 100.0, 101.0) == "error"  # only +1%


def test_evaluate_sell_correct():
    """A 'vender' recommendation is correct if price fell > 2%."""
    from services.recommendation_tracker import _evaluate_recommendation

    assert _evaluate_recommendation("vender", 100.0, 97.0) == "acierto"
    assert _evaluate_recommendation("vender", 100.0, 99.0) == "error"  # only -1%


def test_evaluate_mantener_correct():
    """A 'mantener' recommendation is correct if abs(change) <= 5%."""
    from services.recommendation_tracker import _evaluate_recommendation

    assert _evaluate_recommendation("mantener", 100.0, 103.0) == "acierto"
    assert _evaluate_recommendation("mantener", 100.0, 108.0) == "error"  # +8%


@pytest.mark.asyncio
async def test_update_pending_recommendations_calls_update():
    """update_pending_recommendations should call update_ai_recommendation_result for evaluable records."""
    from services.recommendation_tracker import update_pending_recommendations

    rec = _pending_rec("AAPL", "comprar", 100.0, days_ago=10)

    # Simulate price 5 business days later = 103 (acierto), 10 days = 108 (acierto)
    def fake_get_price(symbol, ref_date, n_days):
        return {5: 103.0, 10: 108.0, 20: None}.get(n_days)

    mock_update = AsyncMock()

    with (
        patch("services.recommendation_tracker.get_pending_ai_recommendations", new=AsyncMock(return_value=[rec])),
        patch("services.recommendation_tracker.update_ai_recommendation_result", new=mock_update),
        patch("services.recommendation_tracker._get_price_on_business_day", side_effect=fake_get_price),
    ):
        await update_pending_recommendations()

    mock_update.assert_called_once()
    call_kwargs = mock_update.call_args.kwargs
    assert call_kwargs["result_5d"] == "acierto"
    assert call_kwargs["result_10d"] == "acierto"
    assert call_kwargs.get("result_20d") is None  # not enough data yet


@pytest.mark.asyncio
async def test_update_pending_skips_if_no_data():
    """update_pending_recommendations should skip horizons with no available price data."""
    from services.recommendation_tracker import update_pending_recommendations

    rec = _pending_rec("AAPL", "comprar", 100.0, days_ago=2)  # only 2 days old

    def fake_get_price(symbol, ref_date, n_days):
        return None  # no data yet for any horizon

    mock_update = AsyncMock()

    with (
        patch("services.recommendation_tracker.get_pending_ai_recommendations", new=AsyncMock(return_value=[rec])),
        patch("services.recommendation_tracker.update_ai_recommendation_result", new=mock_update),
        patch("services.recommendation_tracker._get_price_on_business_day", side_effect=fake_get_price),
    ):
        await update_pending_recommendations()

    mock_update.assert_not_called()
