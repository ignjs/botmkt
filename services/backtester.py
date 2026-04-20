import asyncio
import time
from typing import Dict

import numpy as np
import pandas as pd
import yfinance as yf


def _compute_indicators(close: pd.Series) -> pd.DataFrame:
    df = pd.DataFrame({"close": close.astype(float)})
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean().replace(0, np.nan)
    rs = avg_gain / avg_loss
    df["rsi"] = 100 - (100 / (1 + rs))

    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    return df.dropna()


def _build_summary(symbol: str, metrics: Dict) -> str:
    warning = ""
    if metrics["signals_detected"] < 5:
        warning = f"\n⚠️ Muestra pequeña (n={metrics['signals_detected']}). Interpretar con cautela."

    return (
        f"📊 *Backtest RSI+MACD en {symbol}* (últimos 2 años)\n"
        f"Señales detectadas: {metrics['signals_detected']}\n"
        f"Win rate: {metrics['win_rate_pct']:.0f}% ({metrics['wins']}/{metrics['signals_detected']} correctas a 10 días)\n"
        f"Retorno promedio por señal: {metrics['avg_return_pct']:+.1f}%\n"
        f"Mejor caso: {metrics['best_return_pct']:+.1f}% | Peor caso: {metrics['worst_return_pct']:+.1f}%"
        f"{warning}"
    )


async def run_backtest(symbol: str) -> Dict:
    start_ts = time.perf_counter()

    def _download() -> pd.DataFrame:
        return yf.Ticker(symbol).history(period="2y", interval="1d")

    loop = asyncio.get_event_loop()
    hist = await loop.run_in_executor(None, _download)
    if hist.empty or "Close" not in hist.columns:
        return {
            "symbol": symbol,
            "signals_detected": 0,
            "wins": 0,
            "win_rate_pct": 0.0,
            "avg_return_pct": 0.0,
            "best_return_pct": 0.0,
            "worst_return_pct": 0.0,
            "elapsed_sec": round(time.perf_counter() - start_ts, 3),
            "summary": f"📊 *Backtest RSI+MACD en {symbol}*\nSin datos suficientes para backtest.",
        }

    data = _compute_indicators(hist["Close"].dropna())
    returns = []

    for idx in range(1, len(data) - 10):
        prev_rsi = float(data["rsi"].iloc[idx - 1])
        curr_rsi = float(data["rsi"].iloc[idx])
        macd = float(data["macd"].iloc[idx])
        signal = float(data["signal"].iloc[idx])

        buy_signal = prev_rsi < 30 <= curr_rsi and macd > signal
        sell_signal = prev_rsi > 70 >= curr_rsi and macd < signal
        if not buy_signal and not sell_signal:
            continue

        entry = float(data["close"].iloc[idx])
        exit_10d = float(data["close"].iloc[idx + 10])
        raw_ret = ((exit_10d - entry) / entry) * 100 if entry else 0.0
        signal_ret = raw_ret if buy_signal else -raw_ret
        returns.append(signal_ret)

    if returns:
        wins = sum(1 for r in returns if r > 0)
        signals = len(returns)
        metrics = {
            "symbol": symbol,
            "signals_detected": signals,
            "wins": wins,
            "win_rate_pct": (wins / signals) * 100,
            "avg_return_pct": float(np.mean(returns)),
            "best_return_pct": float(np.max(returns)),
            "worst_return_pct": float(np.min(returns)),
        }
    else:
        metrics = {
            "symbol": symbol,
            "signals_detected": 0,
            "wins": 0,
            "win_rate_pct": 0.0,
            "avg_return_pct": 0.0,
            "best_return_pct": 0.0,
            "worst_return_pct": 0.0,
        }

    metrics["elapsed_sec"] = round(time.perf_counter() - start_ts, 3)
    metrics["summary"] = _build_summary(symbol, metrics)
    return metrics
