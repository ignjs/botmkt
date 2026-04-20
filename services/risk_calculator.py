import logging
from typing import Dict

import pandas as pd
import yfinance as yf

try:
    import pandas_ta as ta
except Exception:  # pragma: no cover - optional dependency fallback
    ta = None

logger = logging.getLogger(__name__)


def _manual_atr(hist: pd.DataFrame, length: int = 14) -> pd.Series:
    prev_close = hist["Close"].shift(1)
    tr = pd.concat(
        [
            (hist["High"] - hist["Low"]).abs(),
            (hist["High"] - prev_close).abs(),
            (hist["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(length).mean()


async def calculate_atr_stop(symbol: str, entry_price: float, multiplier: float = 2.0) -> Dict[str, float]:
    """Calculate ATR(14)-based dynamic stop-loss for a symbol.

    Returns:
        dict: {"atr": float, "stop_loss": float, "stop_pct": float}
    """
    if entry_price <= 0:
        raise ValueError("entry_price debe ser mayor a 0")

    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="30d", interval="1d")
    if hist.empty:
        raise ValueError(f"No hay datos históricos para {symbol}")

    required_cols = {"High", "Low", "Close"}
    if not required_cols.issubset(hist.columns):
        raise ValueError(f"Datos OHLC incompletos para {symbol}")

    hist = hist.copy()
    hist["High"] = pd.to_numeric(hist["High"], errors="coerce")
    hist["Low"] = pd.to_numeric(hist["Low"], errors="coerce")
    hist["Close"] = pd.to_numeric(hist["Close"], errors="coerce")

    if ta is not None:
        atr_series = ta.atr(
            high=hist["High"],
            low=hist["Low"],
            close=hist["Close"],
            length=14,
        )
    else:
        logger.warning("pandas_ta no disponible; usando cálculo ATR manual")
        atr_series = _manual_atr(hist, length=14)

    if atr_series is None or atr_series.dropna().empty:
        raise ValueError(f"No fue posible calcular ATR para {symbol}")

    atr_value = float(atr_series.dropna().iloc[-1])
    stop_loss = max(float(entry_price) - (atr_value * float(multiplier)), 0.0)
    stop_pct = ((stop_loss / float(entry_price)) - 1.0) * 100.0

    return {
        "atr": round(atr_value, 4),
        "stop_loss": round(stop_loss, 4),
        "stop_pct": round(stop_pct, 4),
    }
