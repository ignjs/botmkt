"""Dynamic stop-loss calculator using ATR (Average True Range)."""
import asyncio
import logging
from typing import Dict

import yfinance as yf

logger = logging.getLogger(__name__)

_ATR_PERIOD = 14
_HISTORY_DAYS = "30d"


def _compute_atr(symbol: str) -> Dict:
    """Download 30 days of data and compute ATR(14) using pandas-ta.

    Args:
        symbol: Ticker symbol.

    Returns:
        dict with keys 'atr', 'close'.
    """
    import pandas_ta as ta  # lazy import to avoid import errors at startup

    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=_HISTORY_DAYS, auto_adjust=True)
    if hist.empty or len(hist) < _ATR_PERIOD + 1:
        raise ValueError(f"Datos insuficientes para calcular ATR de {symbol}")

    atr_series = ta.atr(hist["High"], hist["Low"], hist["Close"], length=_ATR_PERIOD)
    if atr_series is None or atr_series.dropna().empty:
        raise ValueError(f"No se pudo calcular ATR para {symbol}")

    atr_value = float(atr_series.dropna().iloc[-1])
    close_value = float(hist["Close"].iloc[-1])
    return {"atr": atr_value, "close": close_value}


async def calculate_atr_stop(symbol: str, entry_price: float, multiplier: float = 2.0) -> Dict:
    """Calculate the ATR-based dynamic stop-loss for a position.

    Downloads 30 days of daily OHLCV data, computes ATR(14) with pandas-ta, and
    returns the stop-loss price and percentage relative to the entry price.

    Args:
        symbol: Ticker symbol (e.g. 'AAPL').
        entry_price: Average purchase price per unit.
        multiplier: Number of ATR units below entry to place the stop (default 2.0).

    Returns:
        dict with keys:
            - 'atr' (float): ATR value in price units.
            - 'stop_loss' (float): Stop-loss price.
            - 'stop_pct' (float): Stop-loss as % below entry_price (negative).

    Raises:
        ValueError: If data is insufficient or ATR cannot be computed.
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _compute_atr, symbol)

    atr = result["atr"]
    stop_loss = round(entry_price - multiplier * atr, 4)
    stop_pct = round(((stop_loss - entry_price) / entry_price) * 100, 2)

    return {"atr": round(atr, 4), "stop_loss": stop_loss, "stop_pct": stop_pct}
