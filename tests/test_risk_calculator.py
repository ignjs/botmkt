"""Unit tests for services/risk_calculator.py — E1."""
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch


def _make_ohlcv(n: int = 40) -> pd.DataFrame:
    """Create a synthetic OHLCV DataFrame for testing."""
    import numpy as np

    np.random.seed(0)
    close = 200 + np.cumsum(np.random.randn(n))
    high = close + abs(np.random.randn(n)) * 0.5
    low = close - abs(np.random.randn(n)) * 0.5
    df = pd.DataFrame({"Close": close, "High": high, "Low": low, "Volume": 1_000_000})
    return df


@pytest.mark.asyncio
async def test_calculate_atr_stop_returns_correct_keys():
    """calculate_atr_stop should return dict with atr, stop_loss, stop_pct."""
    from services.risk_calculator import calculate_atr_stop

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _make_ohlcv(40)

    with patch("yfinance.Ticker", return_value=mock_ticker):
        result = await calculate_atr_stop("AAPL", 210.0, multiplier=2.0)

    assert isinstance(result, dict)
    assert "atr" in result
    assert "stop_loss" in result
    assert "stop_pct" in result


@pytest.mark.asyncio
async def test_calculate_atr_stop_values():
    """stop_loss = entry_price - 2*ATR and stop_pct < 0."""
    from services.risk_calculator import calculate_atr_stop

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _make_ohlcv(40)

    with patch("yfinance.Ticker", return_value=mock_ticker):
        result = await calculate_atr_stop("AAPL", 210.0, multiplier=2.0)

    assert result["stop_loss"] == pytest.approx(210.0 - 2.0 * result["atr"], abs=0.01)
    assert result["stop_pct"] < 0
    expected_pct = ((result["stop_loss"] - 210.0) / 210.0) * 100
    assert result["stop_pct"] == pytest.approx(expected_pct, abs=0.01)


@pytest.mark.asyncio
async def test_calculate_atr_stop_multiplier():
    """A larger multiplier should produce a wider (lower) stop-loss."""
    from services.risk_calculator import calculate_atr_stop

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _make_ohlcv(40)

    with patch("yfinance.Ticker", return_value=mock_ticker):
        r1 = await calculate_atr_stop("AAPL", 210.0, multiplier=1.0)
        r2 = await calculate_atr_stop("AAPL", 210.0, multiplier=3.0)

    assert r2["stop_loss"] < r1["stop_loss"]


@pytest.mark.asyncio
async def test_calculate_atr_stop_insufficient_data():
    """Should raise ValueError when fewer than ATR_PERIOD+1 bars are available."""
    from services.risk_calculator import calculate_atr_stop

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _make_ohlcv(5)  # only 5 rows

    with patch("yfinance.Ticker", return_value=mock_ticker):
        with pytest.raises(ValueError):
            await calculate_atr_stop("FAKE", 100.0)
