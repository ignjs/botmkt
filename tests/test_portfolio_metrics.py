"""Unit tests for services/portfolio_metrics.py — E3."""
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch


def _make_close_df(symbols: list, n: int = 65) -> pd.DataFrame:
    np.random.seed(42)
    data = {}
    for sym in symbols:
        data[sym] = 100 * np.cumprod(1 + np.random.randn(n) * 0.01)
    return pd.DataFrame(data)


@pytest.mark.asyncio
async def test_sharpe_ratio_positive():
    """Sharpe ratio should be computable and be a float for normal data."""
    from services.portfolio_metrics import compute_portfolio_metrics

    positions = [
        {"symbol": "AAPL", "qty": 10, "precio": 150, "valor": 1500},
        {"symbol": "MSFT", "qty": 5, "precio": 300, "valor": 1500},
    ]

    raw = _make_close_df(["AAPL", "MSFT", "^GSPC"])
    arrays = [["Close"] * 3, ["AAPL", "MSFT", "^GSPC"]]
    raw.columns = pd.MultiIndex.from_arrays(arrays)

    with patch("yfinance.download", return_value=raw):
        result = await compute_portfolio_metrics(positions, benchmark_symbol="^GSPC")

    assert "sharpe" in result
    assert isinstance(result["sharpe"], (float, type(None)))
    assert "beta" in result
    assert "max_drawdown_pct" in result
    assert "hhi" in result


@pytest.mark.asyncio
async def test_hhi_single_position():
    """HHI for a single-position portfolio should equal 1.0 (fully concentrated)."""
    from services.portfolio_metrics import compute_portfolio_metrics

    positions = [{"symbol": "AAPL", "qty": 10, "precio": 150, "valor": 1500}]

    raw = _make_close_df(["AAPL", "^GSPC"])
    arrays = [["Close"] * 2, ["AAPL", "^GSPC"]]
    raw.columns = pd.MultiIndex.from_arrays(arrays)

    with patch("yfinance.download", return_value=raw):
        result = await compute_portfolio_metrics(positions, benchmark_symbol="^GSPC")

    assert result["hhi"] == pytest.approx(1.0, abs=0.01)


def test_hhi_equal_weights():
    """HHI for equal weights should equal 1/n."""
    from services.portfolio_metrics import compute_hhi

    weights = {"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25}
    assert compute_hhi(weights) == pytest.approx(0.25, abs=1e-4)


def test_sharpe_calculation():
    """compute_sharpe_ratio should return None when returns have zero variance."""
    from services.portfolio_metrics import compute_sharpe_ratio
    import pandas as pd

    # When all returns are identical, std = 0 → Sharpe is undefined (None)
    daily_rf = (1 + 5.0 / 100) ** (1 / 252) - 1
    returns = pd.Series([daily_rf] * 252)
    sharpe = compute_sharpe_ratio(returns, risk_free_rate=5.0)
    assert sharpe is None  # std=0 → undefined

    # With varying returns, Sharpe should be a finite float
    import numpy as np
    np.random.seed(1)
    varying = pd.Series(np.random.randn(252) * 0.01)
    sharpe2 = compute_sharpe_ratio(varying, risk_free_rate=5.0)
    assert isinstance(sharpe2, float)


def test_max_drawdown_negative():
    """Max drawdown should be negative (or zero) and never positive."""
    from services.portfolio_metrics import compute_max_drawdown
    import pandas as pd

    returns = pd.Series([0.01, 0.01, -0.05, -0.03, 0.02, 0.01])
    dd = compute_max_drawdown(returns)
    assert dd <= 0.0


@pytest.mark.asyncio
async def test_empty_portfolio_returns_none_metrics():
    """Empty portfolio should return None for all metric values."""
    from services.portfolio_metrics import compute_portfolio_metrics

    result = await compute_portfolio_metrics([])
    assert result["sharpe"] is None
    assert result["beta"] is None
    assert result["max_drawdown_pct"] is None
    assert result["hhi"] is None
