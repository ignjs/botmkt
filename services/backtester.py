"""RSI+MACD backtest engine using pure pandas — no extra dependencies."""
import asyncio
import logging
from typing import Dict

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

_HISTORY_PERIOD = "2y"
_RSI_PERIOD = 14
_MACD_FAST = 12
_MACD_SLOW = 26
_MACD_SIGNAL = 9
_EVAL_DAYS = 10         # business days for evaluating each signal
_MIN_SIGNALS = 5        # minimum signals for a meaningful result


def _compute_rsi(close: pd.Series, period: int = _RSI_PERIOD) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    roll_up = up.rolling(period).mean()
    roll_down = down.rolling(period).mean()
    rs = roll_up / roll_down
    return 100 - (100 / (1 + rs))


def _compute_macd(close: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Return (macd_line, signal_line)."""
    exp_fast = close.ewm(span=_MACD_FAST, adjust=False).mean()
    exp_slow = close.ewm(span=_MACD_SLOW, adjust=False).mean()
    macd = exp_fast - exp_slow
    signal = macd.ewm(span=_MACD_SIGNAL, adjust=False).mean()
    return macd, signal


def _detect_signals(hist: pd.DataFrame) -> pd.DataFrame:
    """Detect RSI+MACD buy and sell crossover signals.

    Buy signal:  RSI crosses up through 30 AND MACD > Signal at that bar.
    Sell signal: RSI crosses down through 70 AND MACD < Signal at that bar.

    Returns a DataFrame with columns: date, signal ('buy'/'sell'), entry_price.
    """
    close = hist["Close"]
    rsi = _compute_rsi(close)
    macd, signal = _compute_macd(close)

    rsi_prev = rsi.shift(1)
    macd_line = macd
    signal_line = signal

    buy_mask = (rsi_prev < 30) & (rsi >= 30) & (macd_line > signal_line)
    sell_mask = (rsi_prev > 70) & (rsi <= 70) & (macd_line < signal_line)

    signals = []
    for i, (ts, row) in enumerate(hist.iterrows()):
        if buy_mask.iloc[i]:
            signals.append({"date": ts, "signal": "buy", "entry_price": float(row["Close"]), "idx": i})
        elif sell_mask.iloc[i]:
            signals.append({"date": ts, "signal": "sell", "entry_price": float(row["Close"]), "idx": i})

    return pd.DataFrame(signals) if signals else pd.DataFrame(columns=["date", "signal", "entry_price", "idx"])


def _evaluate_signals(hist: pd.DataFrame, signals_df: pd.DataFrame, eval_days: int = _EVAL_DAYS) -> pd.DataFrame:
    """Compute the return at eval_days business days for each signal.

    For a buy signal: win if return > 0.
    For a sell signal: win if return < 0.
    """
    results = []
    close = hist["Close"].reset_index(drop=True)

    for _, sig in signals_df.iterrows():
        idx = int(sig["idx"])
        exit_idx = idx + eval_days
        if exit_idx >= len(close):
            continue  # not enough future data
        entry = sig["entry_price"]
        exit_price = float(close.iloc[exit_idx])
        ret = (exit_price - entry) / entry
        if sig["signal"] == "buy":
            win = ret > 0
        else:
            win = ret < 0
        results.append({
            "signal": sig["signal"],
            "entry_price": entry,
            "exit_price": exit_price,
            "return_pct": round(ret * 100, 2),
            "win": win,
        })

    return pd.DataFrame(results) if results else pd.DataFrame(columns=["signal", "entry_price", "exit_price", "return_pct", "win"])


def _run_backtest_sync(symbol: str) -> Dict:
    """Download 2 years of data and run the RSI+MACD backtest.

    Returns a results dict with n_signals, win_rate, avg_return, best, worst, insufficient.
    """
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=_HISTORY_PERIOD, auto_adjust=True)
    if hist.empty or len(hist) < _MACD_SLOW + _RSI_PERIOD + _EVAL_DAYS:
        return {
            "n_signals": 0,
            "win_rate": None,
            "avg_return_pct": None,
            "best_pct": None,
            "worst_pct": None,
            "insufficient": True,
        }

    signals_df = _detect_signals(hist)
    if signals_df.empty:
        return {
            "n_signals": 0,
            "win_rate": None,
            "avg_return_pct": None,
            "best_pct": None,
            "worst_pct": None,
            "insufficient": True,
        }

    results_df = _evaluate_signals(hist, signals_df)
    n_signals = len(results_df)
    insufficient = n_signals < _MIN_SIGNALS

    if n_signals == 0:
        return {
            "n_signals": 0,
            "win_rate": None,
            "avg_return_pct": None,
            "best_pct": None,
            "worst_pct": None,
            "insufficient": True,
        }

    win_rate = round(results_df["win"].sum() / n_signals * 100, 1)
    avg_return = round(float(results_df["return_pct"].mean()), 2)
    best = round(float(results_df["return_pct"].max()), 2)
    worst = round(float(results_df["return_pct"].min()), 2)

    return {
        "n_signals": n_signals,
        "win_rate": win_rate,
        "avg_return_pct": avg_return,
        "best_pct": best,
        "worst_pct": worst,
        "insufficient": insufficient,
    }


async def run_rsi_macd_backtest(symbol: str) -> Dict:
    """Run RSI+MACD backtest asynchronously.

    Args:
        symbol: Ticker symbol.

    Returns:
        dict with keys: n_signals, win_rate, avg_return_pct, best_pct, worst_pct, insufficient.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run_backtest_sync, symbol)


def format_backtest_summary(symbol: str, result: Dict) -> str:
    """Format the backtest results as a Telegram-ready Markdown string.

    Args:
        symbol: Ticker symbol.
        result: Dict returned by run_rsi_macd_backtest.

    Returns:
        str: Formatted Markdown summary.
    """
    if result.get("n_signals", 0) == 0:
        return (
            f"📊 *Backtest RSI+MACD en {symbol}* (últimos 2 años)\n"
            "Sin señales detectadas en el período."
        )

    n = result["n_signals"]
    wr = result["win_rate"]
    avg = result["avg_return_pct"]
    best = result["best_pct"]
    worst = result["worst_pct"]

    wins = round(n * wr / 100)
    warning = (
        f"\n⚠️ Muestra pequeña (n={n}). Interpretar con cautela."
        if result.get("insufficient") else ""
    )

    return (
        f"📊 *Backtest RSI+MACD en {symbol}* (últimos 2 años)\n"
        f"Señales detectadas: {n}\n"
        f"Win rate: {wr:.0f}% ({wins}/{n} correctas a {_EVAL_DAYS} días)\n"
        f"Retorno promedio por señal: {avg:+.1f}%\n"
        f"Mejor caso: {best:+.1f}% | Peor caso: {worst:+.1f}%"
        f"{warning}"
    )
