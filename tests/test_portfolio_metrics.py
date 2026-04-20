import pandas as pd
import pytest

from services.portfolio_metrics import calculate_portfolio_metrics


@pytest.mark.asyncio
async def test_portfolio_metrics_with_simulated_data(monkeypatch):
    async def _fake_positions(_):
        return [
            {"symbol": "AAPL", "quantity": 10, "avg_buy_price": 200},
            {"symbol": "MSFT", "quantity": 5, "avg_buy_price": 300},
        ]

    dates = pd.date_range("2025-01-01", periods=100, freq="B")
    aapl = pd.Series([100 + i * 0.5 for i in range(100)], index=dates)
    msft = pd.Series([150 + i * 0.4 for i in range(100)], index=dates)
    bench = pd.Series([90 + i * 0.3 for i in range(100)], index=dates)

    prices = pd.DataFrame({
        ("Close", "AAPL"): aapl,
        ("Close", "MSFT"): msft,
    }, index=dates)
    prices.columns = pd.MultiIndex.from_tuples(prices.columns)

    bench_df = pd.DataFrame({"Close": bench}, index=dates)

    def _fake_download(symbols, period=None, auto_adjust=True, progress=False):
        if symbols == "^GSPC":
            return bench_df
        return prices

    monkeypatch.setattr("services.portfolio_metrics.get_positions", _fake_positions)
    monkeypatch.setattr("services.portfolio_metrics.yf.download", _fake_download)

    result = await calculate_portfolio_metrics(123)

    assert result["empty"] is False
    assert "sharpe_ratio" in result
    assert "beta" in result
    assert "max_drawdown" in result
    assert "hhi" in result
    assert result["portfolio_size"] == 2


@pytest.mark.asyncio
async def test_portfolio_metrics_single_position(monkeypatch):
    async def _fake_positions(_):
        return [{"symbol": "AAPL", "quantity": 10, "avg_buy_price": 200}]

    dates = pd.date_range("2025-01-01", periods=100, freq="B")
    close = pd.Series([100 + i * 0.5 for i in range(100)], index=dates)
    bench = pd.Series([100 + i * 0.2 for i in range(100)], index=dates)

    symbol_df = pd.DataFrame({"Close": close}, index=dates)
    bench_df = pd.DataFrame({"Close": bench}, index=dates)

    def _fake_download(symbols, period=None, auto_adjust=True, progress=False):
        if symbols == "^GSPC":
            return bench_df
        return symbol_df

    monkeypatch.setattr("services.portfolio_metrics.get_positions", _fake_positions)
    monkeypatch.setattr("services.portfolio_metrics.yf.download", _fake_download)

    result = await calculate_portfolio_metrics(321)

    assert result["portfolio_size"] == 1
    assert result["dominant_position"]["symbol"] == "AAPL"
    assert isinstance(result["sharpe_ratio"], float)
    assert isinstance(result["beta"], float)
