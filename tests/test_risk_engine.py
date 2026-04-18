"""Tests for services/risk_engine.py."""
import pandas as pd
import numpy as np
import pytest
from unittest.mock import patch, MagicMock


def _make_close_df(symbols: list[str], n: int = 252) -> pd.DataFrame:
    """Create a fake OHLCV-style close price DataFrame."""
    np.random.seed(42)
    data = {}
    for sym in symbols:
        prices = 100 * np.cumprod(1 + np.random.randn(n) * 0.01)
        data[sym] = prices
    return pd.DataFrame(data)


def _make_multi_index_raw(symbols: list[str], n: int = 252):
    """Return a DataFrame with MultiIndex columns (Close, Open, ...) as yfinance would."""
    close_df = _make_close_df(symbols, n)
    arrays = [["Close"] * len(symbols), symbols]
    tuples = list(zip(*arrays))
    multi_index = pd.MultiIndex.from_tuples(tuples)
    df = close_df.copy()
    df.columns = multi_index
    return df


@pytest.mark.asyncio
async def test_calcular_metricas_cartera_single_symbol():
    """Single symbol should compute metrics without error."""
    from services.risk_engine import calcular_metricas_cartera

    posiciones = [{"symbol": "AAPL", "qty": 10, "precio": 150, "valor": 1500}]

    # yfinance flat format for single symbol: columns are Open, High, Low, Close, Volume
    np.random.seed(42)
    prices = 100 * np.cumprod(1 + np.random.randn(252) * 0.01)
    flat_df = pd.DataFrame({"Close": prices})

    with patch("yfinance.download", return_value=flat_df):
        result = await calcular_metricas_cartera(posiciones)

    assert "var_95_pct" in result
    assert "sharpe" in result
    assert "max_drawdown_pct" in result
    assert "hhi" in result
    assert result["symbols_used"] == ["AAPL"]
    assert result["symbols_excluded"] == []
    assert result["hhi"] == pytest.approx(10000.0, abs=1)  # 100% in one stock = 10000


@pytest.mark.asyncio
async def test_calcular_metricas_cartera_multiple_symbols():
    """Multiple symbols should compute correct weights and metrics."""
    from services.risk_engine import calcular_metricas_cartera

    posiciones = [
        {"symbol": "AAPL", "qty": 10, "precio": 150, "valor": 1500},
        {"symbol": "MSFT", "qty": 5, "precio": 300, "valor": 1500},
    ]
    raw = _make_multi_index_raw(["AAPL", "MSFT"])

    with patch("yfinance.download", return_value=raw):
        result = await calcular_metricas_cartera(posiciones)

    assert set(result["symbols_used"]) == {"AAPL", "MSFT"}
    assert result["symbols_excluded"] == []
    total_weight = sum(result["weights"].values())
    assert total_weight == pytest.approx(1.0, abs=1e-6)
    assert result["portfolio_value"] == pytest.approx(3000.0)


@pytest.mark.asyncio
async def test_excluye_simbolo_sin_datos():
    """Symbols with empty data should be excluded and reported."""
    from services.risk_engine import calcular_metricas_cartera

    posiciones = [
        {"symbol": "AAPL", "qty": 10, "precio": 150, "valor": 1500},
        {"symbol": "FAKESYM", "qty": 5, "precio": 10, "valor": 50},
    ]

    # Only AAPL gets data; FAKESYM column is all NaN
    close_df = _make_close_df(["AAPL"])
    close_df["FAKESYM"] = np.nan

    # Wrap as MultiIndex since yfinance uses it for 2 symbols
    arrays = [["Close", "Close"], ["AAPL", "FAKESYM"]]
    close_df.columns = pd.MultiIndex.from_arrays(arrays)

    with patch("yfinance.download", return_value=close_df):
        result = await calcular_metricas_cartera(posiciones)

    assert "AAPL" in result["symbols_used"]
    assert "FAKESYM" in result["symbols_excluded"]


@pytest.mark.asyncio
async def test_formatear_metricas_para_telegram_semaforos():
    """Emoji semaphores should match thresholds for Sharpe and HHI."""
    from services.risk_engine import formatear_metricas_para_telegram

    # Case: excellent Sharpe (>1) and low HHI (<1500) → both green
    metricas_green = {
        "var_95_pct": 1.5,
        "var_95_usd": 150.0,
        "sharpe": 1.5,
        "max_drawdown_pct": -5.0,
        "hhi": 1200.0,
        "symbols_excluded": [],
    }
    text = formatear_metricas_para_telegram(metricas_green)
    assert "🟢" in text
    assert "🔴" not in text

    # Case: negative Sharpe (<0) and high HHI (>2500) → both red
    metricas_red = {
        "var_95_pct": 3.0,
        "var_95_usd": 300.0,
        "sharpe": -0.5,
        "max_drawdown_pct": -20.0,
        "hhi": 3000.0,
        "symbols_excluded": [],
    }
    text_red = formatear_metricas_para_telegram(metricas_red)
    assert "🔴" in text_red
    assert "🟢" not in text_red

    # Case: moderate Sharpe (0-1) and moderate HHI (1500-2500) → both yellow
    metricas_yellow = {
        "var_95_pct": 2.0,
        "var_95_usd": 200.0,
        "sharpe": 0.5,
        "max_drawdown_pct": -10.0,
        "hhi": 2000.0,
        "symbols_excluded": [],
    }
    text_yellow = formatear_metricas_para_telegram(metricas_yellow)
    assert "🟡" in text_yellow

    # Case: excluded symbols should appear in note
    metricas_excl = dict(metricas_green)
    metricas_excl["symbols_excluded"] = ["FAKESYM"]
    text_excl = formatear_metricas_para_telegram(metricas_excl)
    assert "FAKESYM" in text_excl
    assert "Sin datos" in text_excl
