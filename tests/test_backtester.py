"""Unit tests for services/backtester.py — E6."""
import numpy as np
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch


def _make_hist(n: int = 300) -> pd.DataFrame:
    """Create a synthetic OHLCV DataFrame with a known buy signal."""
    np.random.seed(7)
    close = 100.0 * np.cumprod(1 + np.random.randn(n) * 0.01)
    df = pd.DataFrame({
        "Close": close,
        "High": close * 1.005,
        "Low": close * 0.995,
        "Volume": np.random.randint(1_000_000, 5_000_000, n).astype(float),
    })
    return df


@pytest.mark.asyncio
async def test_run_rsi_macd_backtest_returns_expected_keys():
    """run_rsi_macd_backtest should return a dict with all required keys."""
    from services.backtester import run_rsi_macd_backtest

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _make_hist(300)

    with patch("yfinance.Ticker", return_value=mock_ticker):
        result = await run_rsi_macd_backtest("AAPL")

    required_keys = {"n_signals", "win_rate", "avg_return_pct", "best_pct", "worst_pct", "insufficient"}
    assert required_keys.issubset(result.keys())


@pytest.mark.asyncio
async def test_run_rsi_macd_backtest_insufficient_data():
    """When fewer than 60 bars are available, insufficient should be True."""
    from services.backtester import run_rsi_macd_backtest

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _make_hist(30)  # too short

    with patch("yfinance.Ticker", return_value=mock_ticker):
        result = await run_rsi_macd_backtest("AAPL")

    assert result["insufficient"] is True


def test_detect_signals_produces_dataframe():
    """_detect_signals should return a DataFrame with expected columns."""
    from services.backtester import _detect_signals

    hist = _make_hist(300)
    signals = _detect_signals(hist)

    assert isinstance(signals, pd.DataFrame)
    assert "signal" in signals.columns or signals.empty


def test_evaluate_signals_win_rate_in_bounds():
    """Win rates from _evaluate_signals should be between 0 and 100."""
    from services.backtester import _detect_signals, _evaluate_signals

    hist = _make_hist(300)
    signals = _detect_signals(hist)
    if signals.empty:
        pytest.skip("No signals generated for this seed")

    results = _evaluate_signals(hist, signals)
    if results.empty:
        pytest.skip("No evaluable results (not enough future data)")

    win_rate = results["win"].sum() / len(results) * 100
    assert 0 <= win_rate <= 100


def test_format_backtest_summary_no_signals():
    """format_backtest_summary with zero signals should mention 'Sin señales'."""
    from services.backtester import format_backtest_summary

    result = {"n_signals": 0, "win_rate": None, "avg_return_pct": None, "best_pct": None, "worst_pct": None, "insufficient": True}
    text = format_backtest_summary("AAPL", result)
    assert "Sin señales" in text


def test_format_backtest_summary_with_signals():
    """format_backtest_summary with results should include n_signals and win_rate."""
    from services.backtester import format_backtest_summary

    result = {
        "n_signals": 12,
        "win_rate": 67.0,
        "avg_return_pct": 3.2,
        "best_pct": 14.1,
        "worst_pct": -8.3,
        "insufficient": False,
    }
    text = format_backtest_summary("AAPL", result)
    assert "12" in text
    assert "67" in text
    assert "3.2" in text
