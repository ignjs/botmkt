import pandas as pd
import pytest

from services.backtester import run_backtest


@pytest.mark.asyncio
async def test_run_backtest_returns_expected_keys(monkeypatch):
    dates = pd.date_range("2024-01-01", periods=520, freq="B")
    close = pd.Series([100 + (i * 0.2) + ((-1) ** i) * 2 for i in range(520)], index=dates)
    hist = pd.DataFrame({"Close": close}, index=dates)

    class FakeTicker:
        def history(self, period="2y", interval="1d"):
            return hist

    monkeypatch.setattr("services.backtester.yf.Ticker", lambda symbol: FakeTicker())

    result = await run_backtest("AAPL")

    assert set(result.keys()) >= {
        "symbol",
        "signals_detected",
        "win_rate_pct",
        "avg_return_pct",
        "best_return_pct",
        "worst_return_pct",
        "elapsed_sec",
        "summary",
    }
    assert result["elapsed_sec"] <= 3.0


@pytest.mark.asyncio
async def test_run_backtest_warns_on_small_sample(monkeypatch):
    dates = pd.date_range("2025-01-01", periods=40, freq="B")
    close = pd.Series([100 + i * 0.05 for i in range(40)], index=dates)
    hist = pd.DataFrame({"Close": close}, index=dates)

    class FakeTicker:
        def history(self, period="2y", interval="1d"):
            return hist

    monkeypatch.setattr("services.backtester.yf.Ticker", lambda symbol: FakeTicker())

    result = await run_backtest("MSFT")

    if result["signals_detected"] < 5:
        assert "Muestra pequeña" in result["summary"]
