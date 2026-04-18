"""Tests for services/optimizer.py."""
import pandas as pd
import numpy as np
import pytest
from unittest.mock import patch


def _make_close_df(symbols: list[str], n: int = 252) -> pd.DataFrame:
    """Create deterministic close price data."""
    np.random.seed(99)
    data = {}
    for sym in symbols:
        prices = 100 * np.cumprod(1 + np.random.randn(n) * 0.01)
        data[sym] = prices
    return pd.DataFrame(data)


def _make_multi_index_raw(symbols: list[str], n: int = 252):
    """Return MultiIndex DataFrame as yfinance would for multiple symbols."""
    close_df = _make_close_df(symbols, n)
    arrays = [["Close"] * len(symbols), symbols]
    close_df.columns = pd.MultiIndex.from_arrays(arrays)
    return close_df


@pytest.mark.asyncio
async def test_optimizar_cartera_returns_valid_weights():
    """Optimizer should return a result dict with all expected keys."""
    from services.optimizer import optimizar_cartera

    posiciones = [
        {"symbol": "AAPL", "qty": 10, "precio": 150, "valor": 1500},
        {"symbol": "MSFT", "qty": 5, "precio": 300, "valor": 1500},
        {"symbol": "GOOG", "qty": 2, "precio": 2800, "valor": 5600},
    ]
    perfil = {"risk_tolerance": 5, "max_position_pct": 60}
    raw = _make_multi_index_raw(["AAPL", "MSFT", "GOOG"])

    with patch("yfinance.download", return_value=raw):
        result = await optimizar_cartera(posiciones, perfil)

    assert "optimal_weights" in result
    assert "expected_return_annual" in result
    assert "expected_vol_annual" in result
    assert "expected_sharpe" in result
    assert "current_weights" in result
    assert "operations" in result
    assert len(result["operations"]) == 3


@pytest.mark.asyncio
async def test_weights_sum_to_one():
    """Optimal weights must sum to 1.0 within tolerance."""
    from services.optimizer import optimizar_cartera

    posiciones = [
        {"symbol": "AAPL", "qty": 10, "precio": 150, "valor": 1500},
        {"symbol": "MSFT", "qty": 5, "precio": 300, "valor": 1500},
        {"symbol": "TSLA", "qty": 3, "precio": 250, "valor": 750},
    ]
    perfil = {"risk_tolerance": 7, "max_position_pct": 50}
    raw = _make_multi_index_raw(["AAPL", "MSFT", "TSLA"])

    with patch("yfinance.download", return_value=raw):
        result = await optimizar_cartera(posiciones, perfil)

    total = sum(result["optimal_weights"].values())
    assert total == pytest.approx(1.0, abs=1e-4)


@pytest.mark.asyncio
async def test_low_risk_tolerance_constraint():
    """Low risk tolerance (3) should still produce a valid optimization."""
    from services.optimizer import optimizar_cartera

    posiciones = [
        {"symbol": "AAPL", "qty": 10, "precio": 150, "valor": 1500},
        {"symbol": "MSFT", "qty": 5, "precio": 300, "valor": 1500},
        {"symbol": "BND", "qty": 100, "precio": 75, "valor": 7500},
    ]
    perfil = {"risk_tolerance": 3, "max_position_pct": 60}
    raw = _make_multi_index_raw(["AAPL", "MSFT", "BND"])

    with patch("yfinance.download", return_value=raw):
        result = await optimizar_cartera(posiciones, perfil)

    total = sum(result["optimal_weights"].values())
    assert total == pytest.approx(1.0, abs=1e-4)


@pytest.mark.asyncio
async def test_single_symbol_raises_error():
    """Less than 2 valid symbols should raise ValueError."""
    from services.optimizer import optimizar_cartera

    posiciones = [{"symbol": "AAPL", "qty": 10, "precio": 150, "valor": 1500}]
    perfil = {"risk_tolerance": 5, "max_position_pct": 25}

    # yfinance flat format: columns are Open, High, Low, Close, Volume
    np.random.seed(42)
    prices = 100 * np.cumprod(1 + np.random.randn(252) * 0.01)
    flat_df = pd.DataFrame({"Close": prices})

    with patch("yfinance.download", return_value=flat_df):
        with pytest.raises(ValueError, match="al menos 2 símbolos"):
            await optimizar_cartera(posiciones, perfil)


def test_formatear_rebalanceo_para_telegram_contains_disclaimer():
    """Formatted output should include disclaimer and key metrics."""
    from services.optimizer import formatear_rebalanceo_para_telegram

    resultado = {
        "expected_return_annual": 12.5,
        "expected_vol_annual": 18.3,
        "expected_sharpe": 0.822,
        "operations": [
            {"symbol": "AAPL", "current_pct": 40.0, "target_pct": 35.0, "delta_pct": -5.0},
            {"symbol": "MSFT", "current_pct": 35.0, "target_pct": 40.0, "delta_pct": 5.0},
            {"symbol": "GOOG", "current_pct": 25.0, "target_pct": 25.0, "delta_pct": 0.0},
        ],
    }

    text = formatear_rebalanceo_para_telegram(resultado)

    assert "Disclaimer" in text
    assert "Markowitz" in text
    assert "12.50%" in text
    assert "AAPL" in text
    assert "MSFT" in text
