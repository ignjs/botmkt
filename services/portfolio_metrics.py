"""Quantitative portfolio metrics: Sharpe Ratio, Beta, Max Drawdown, HHI."""
import asyncio
import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf

from config import Config

logger = logging.getLogger(__name__)

_TRADING_DAYS_PER_YEAR = 252
_HISTORY_PERIOD = "3mo"


def _download_close(symbols: List[str]) -> pd.DataFrame:
    """Download 90 days of adjusted close prices for the given symbols.

    Returns a DataFrame with one column per symbol.
    """
    raw = yf.download(symbols, period=_HISTORY_PERIOD, auto_adjust=True, progress=False)
    if raw.empty:
        return pd.DataFrame()

    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"] if "Close" in raw.columns.get_level_values(0) else pd.DataFrame()
    else:
        close = raw[["Close"]] if len(symbols) == 1 else raw
        if len(symbols) == 1:
            close.columns = [symbols[0]]
    return close


def compute_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 5.0) -> Optional[float]:
    """Compute annualised Sharpe Ratio.

    Args:
        returns: Daily portfolio returns series.
        risk_free_rate: Annual risk-free rate as a percentage (default from Config).

    Returns:
        float: Sharpe ratio, or None if insufficient data.
    """
    if returns.empty or returns.std() == 0:
        return None
    daily_rf = (1 + risk_free_rate / 100) ** (1 / _TRADING_DAYS_PER_YEAR) - 1
    excess = returns - daily_rf
    sharpe = (excess.mean() / excess.std()) * np.sqrt(_TRADING_DAYS_PER_YEAR)
    return round(float(sharpe), 4)


def compute_beta(portfolio_returns: pd.Series, benchmark_returns: pd.Series) -> Optional[float]:
    """Compute Beta of the portfolio vs. a benchmark.

    Args:
        portfolio_returns: Daily portfolio return series.
        benchmark_returns: Daily benchmark return series.

    Returns:
        float: Beta, or None if insufficient data.
    """
    aligned = pd.concat([portfolio_returns, benchmark_returns], axis=1).dropna()
    if len(aligned) < 10:
        return None
    cov = np.cov(aligned.iloc[:, 0], aligned.iloc[:, 1])
    var_bench = cov[1, 1]
    if var_bench == 0:
        return None
    beta = cov[0, 1] / var_bench
    return round(float(beta), 4)


def compute_max_drawdown(returns: pd.Series) -> float:
    """Compute the maximum drawdown (as a negative percentage).

    Args:
        returns: Daily return series.

    Returns:
        float: Max drawdown percentage (e.g. -12.3 means -12.3%).
    """
    cum = (1 + returns).cumprod()
    rolling_max = cum.cummax()
    drawdown = (cum - rolling_max) / rolling_max
    max_dd = float(drawdown.min()) * 100
    return round(max_dd, 2)


def compute_hhi(weights: Dict[str, float]) -> float:
    """Compute the Herfindahl-Hirschman Index (HHI) of portfolio concentration.

    HHI = sum of squared weights (expressed as fractions 0-1).
    Result is returned as a fraction (0-1), where:
    - > 0.25 = concentrated
    - < 0.10 = diversified

    Args:
        weights: Dict mapping symbol -> weight (sum must equal 1).

    Returns:
        float: HHI value between 0 and 1.
    """
    hhi = sum(w ** 2 for w in weights.values())
    return round(float(hhi), 4)


async def compute_portfolio_metrics(
    positions: List[Dict],
    risk_free_rate: Optional[float] = None,
    benchmark_symbol: Optional[str] = None,
) -> Dict:
    """Compute all portfolio metrics for a given list of positions.

    Args:
        positions: List of position dicts (must contain 'symbol', 'valor').
        risk_free_rate: Annual risk-free rate %. Defaults to Config.RISK_FREE_RATE.
        benchmark_symbol: Benchmark ticker. Defaults to Config.BENCHMARK_SYMBOL.

    Returns:
        dict with keys: sharpe, beta, max_drawdown_pct, hhi, weights,
                        dominant_symbol, benchmark_symbol, risk_free_rate,
                        symbols_used, symbols_excluded.
    """
    if risk_free_rate is None:
        risk_free_rate = float(getattr(Config, "RISK_FREE_RATE", 5.0))
    if benchmark_symbol is None:
        benchmark_symbol = getattr(Config, "BENCHMARK_SYMBOL", "^GSPC")

    if not positions:
        return {
            "sharpe": None,
            "beta": None,
            "max_drawdown_pct": None,
            "hhi": None,
            "weights": {},
            "dominant_symbol": None,
            "benchmark_symbol": benchmark_symbol,
            "risk_free_rate": risk_free_rate,
            "symbols_used": [],
            "symbols_excluded": [],
        }

    total_value = sum(float(p["valor"]) for p in positions)
    weights = {
        p["symbol"]: float(p["valor"]) / total_value
        for p in positions
        if total_value > 0
    }
    dominant_symbol = max(weights, key=weights.get) if weights else None

    symbols = list(weights.keys())

    loop = asyncio.get_event_loop()

    # Download portfolio symbols + benchmark
    all_symbols = symbols + [benchmark_symbol]
    raw_close = await loop.run_in_executor(None, _download_close, all_symbols)

    symbols_used = []
    symbols_excluded = []
    portfolio_close_parts = []

    if raw_close.empty:
        symbols_excluded = symbols[:]
    else:
        for sym in symbols:
            if sym in raw_close.columns and raw_close[sym].dropna().shape[0] > 10:
                symbols_used.append(sym)
                series = raw_close[sym].dropna()
                w = weights[sym]
                portfolio_close_parts.append(series * w)
            else:
                symbols_excluded.append(sym)

    if not symbols_used:
        return {
            "sharpe": None,
            "beta": None,
            "max_drawdown_pct": None,
            "hhi": None,
            "weights": weights,
            "dominant_symbol": dominant_symbol,
            "benchmark_symbol": benchmark_symbol,
            "risk_free_rate": risk_free_rate,
            "symbols_used": symbols_used,
            "symbols_excluded": symbols_excluded,
        }

    portfolio_value_series = pd.concat(portfolio_close_parts, axis=1).sum(axis=1)
    portfolio_returns = portfolio_value_series.pct_change().dropna()

    sharpe = compute_sharpe_ratio(portfolio_returns, risk_free_rate)
    max_dd = compute_max_drawdown(portfolio_returns)

    # Recompute weights only for used symbols
    used_value = sum(float(p["valor"]) for p in positions if p["symbol"] in symbols_used)
    used_weights = {
        sym: float(p["valor"]) / used_value
        for p in positions
        for sym in [p["symbol"]]
        if sym in symbols_used and used_value > 0
    }
    hhi = compute_hhi(used_weights)

    # Beta vs benchmark
    beta = None
    if benchmark_symbol in raw_close.columns:
        bench_series = raw_close[benchmark_symbol].dropna()
        bench_returns = bench_series.pct_change().dropna()
        beta = compute_beta(portfolio_returns, bench_returns)

    return {
        "sharpe": sharpe,
        "beta": beta,
        "max_drawdown_pct": max_dd,
        "hhi": hhi,
        "weights": used_weights,
        "dominant_symbol": dominant_symbol,
        "benchmark_symbol": benchmark_symbol,
        "risk_free_rate": risk_free_rate,
        "symbols_used": symbols_used,
        "symbols_excluded": symbols_excluded,
    }
