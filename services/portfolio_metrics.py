import asyncio
import logging
from typing import Dict, List

import numpy as np
import pandas as pd
import yfinance as yf

from config.settings import settings
from db import get_positions

logger = logging.getLogger(__name__)
TRADING_DAYS = 252


def _compute_sharpe(port_returns: pd.Series) -> float:
    if port_returns.empty:
        return 0.0
    excess = port_returns - (settings.risk_free_rate / 100.0 / TRADING_DAYS)
    std = port_returns.std(ddof=0)
    if std == 0:
        return 0.0
    return float((excess.mean() / std) * np.sqrt(TRADING_DAYS))


def _compute_beta(port_returns: pd.Series, benchmark_returns: pd.Series) -> float:
    aligned = pd.concat([port_returns, benchmark_returns], axis=1).dropna()
    if aligned.empty:
        return 0.0
    cov = np.cov(aligned.iloc[:, 0], aligned.iloc[:, 1], ddof=0)[0, 1]
    var = np.var(aligned.iloc[:, 1], ddof=0)
    if var == 0:
        return 0.0
    return float(cov / var)


def _compute_max_drawdown(port_returns: pd.Series) -> float:
    if port_returns.empty:
        return 0.0
    curve = (1 + port_returns).cumprod()
    peak = curve.cummax()
    drawdown = (curve / peak) - 1
    return float(drawdown.min())


def _compute_hhi(weights: np.ndarray) -> float:
    if weights.size == 0:
        return 0.0
    return float(np.sum(weights ** 2))


async def calculate_portfolio_metrics(telegram_user_id: int, period: str = "90d") -> Dict:
    positions = await get_positions(telegram_user_id)
    if not positions:
        return {"empty": True}

    symbols = [p["symbol"] for p in positions]

    def _as_close_series(raw: pd.DataFrame) -> pd.Series:
        if raw is None or raw.empty:
            return pd.Series(dtype=float)

        if isinstance(raw.columns, pd.MultiIndex):
            if "Close" not in raw.columns.get_level_values(0):
                return pd.Series(dtype=float)
            close_part = raw["Close"]
            if isinstance(close_part, pd.DataFrame):
                if close_part.empty:
                    return pd.Series(dtype=float)
                return close_part.iloc[:, 0]
            return close_part

        if "Close" in raw.columns:
            close_part = raw["Close"]
            if isinstance(close_part, pd.DataFrame):
                if close_part.empty:
                    return pd.Series(dtype=float)
                return close_part.iloc[:, 0]
            return close_part

        return pd.Series(dtype=float)

    def _download_data() -> tuple[pd.DataFrame, pd.Series]:
        symbols_raw = yf.download(symbols, period=period, auto_adjust=True, progress=False)
        bench_raw = yf.download(settings.benchmark_symbol, period=period, auto_adjust=True, progress=False)

        if isinstance(symbols_raw.columns, pd.MultiIndex):
            close = symbols_raw["Close"]
        else:
            close = symbols_raw[["Close"]].rename(columns={"Close": symbols[0]})

        bench_close = _as_close_series(bench_raw)
        return close, bench_close

    loop = asyncio.get_event_loop()
    close, bench_close = await loop.run_in_executor(None, _download_data)

    clean = pd.DataFrame({s: close[s].dropna() for s in symbols if s in close.columns and not close[s].dropna().empty})
    clean = clean.dropna()
    if clean.empty:
        return {"empty": True}

    latest_prices = clean.iloc[-1]
    position_values = np.array([
        float(p["quantity"]) * float(latest_prices.get(p["symbol"], float(p["avg_buy_price"])))
        for p in positions
        if p["symbol"] in latest_prices.index
    ])

    used_symbols = [p["symbol"] for p in positions if p["symbol"] in latest_prices.index]
    weights = position_values / position_values.sum()

    returns = clean[used_symbols].pct_change().dropna()
    portfolio_returns = pd.Series(returns.values @ weights, index=returns.index)

    benchmark_returns = pd.to_numeric(bench_close, errors="coerce").pct_change().dropna()
    benchmark_returns = benchmark_returns.reindex(portfolio_returns.index).dropna()
    aligned_portfolio = portfolio_returns.reindex(benchmark_returns.index).dropna()

    sharpe = _compute_sharpe(portfolio_returns)
    beta = _compute_beta(aligned_portfolio, benchmark_returns)
    max_drawdown = _compute_max_drawdown(portfolio_returns)
    hhi = _compute_hhi(weights)

    dominant_idx = int(np.argmax(weights))
    dominant_symbol = used_symbols[dominant_idx]
    dominant_weight = float(weights[dominant_idx])

    return {
        "empty": False,
        "period": period,
        "benchmark": settings.benchmark_symbol,
        "sharpe_ratio": round(sharpe, 4),
        "beta": round(beta, 4),
        "max_drawdown": round(max_drawdown, 4),
        "hhi": round(hhi, 4),
        "portfolio_size": len(used_symbols),
        "dominant_position": {
            "symbol": dominant_symbol,
            "weight": round(dominant_weight, 4),
        },
    }


def format_metrics_for_telegram(metrics: Dict) -> str:
    if metrics.get("empty"):
        return "No tienes posiciones en cartera para calcular métricas."

    hhi = float(metrics["hhi"])
    hhi_state = "⚠️ (portafolio concentrado)" if hhi > 0.25 else "✅ (diversificado)"

    return (
        "📊 *Métricas de Portafolio* (últimos 90 días)\n\n"
        f"📈 Sharpe Ratio: {metrics['sharpe_ratio']:.2f}  ✅ (>1 = bueno)\n"
        f"⚖️ Beta vs {metrics['benchmark']}: {metrics['beta']:.2f}\n"
        f"📉 Max Drawdown: {metrics['max_drawdown'] * 100:.1f}%\n"
        f"🎯 Concentración (HHI): {metrics['hhi']:.2f}  {hhi_state}\n\n"
        f"Posición dominante: {metrics['dominant_position']['symbol']} "
        f"({metrics['dominant_position']['weight'] * 100:.1f}%)"
    )
