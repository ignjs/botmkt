"""Recommendation tracker: evaluates pending AI recommendations against actual prices."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import yfinance as yf

from db import get_pending_ai_recommendations, update_ai_recommendation_result

logger = logging.getLogger(__name__)

_THRESHOLDS = {
    "comprar": 0.02,    # acierto if price rose > 2%
    "vender": -0.02,    # acierto if price fell > 2% (i.e. change < -2%)
    "mantener": 0.05,   # acierto if abs(change) <= 5%
}

_BUSINESS_DAYS_MAP = {5: "price_5d", 10: "price_10d", 20: "price_20d"}
_RESULT_MAP = {5: "result_5d", 10: "result_10d", 20: "result_20d"}


def _get_price_on_business_day(symbol: str, reference_date: datetime, n_days: int) -> Optional[float]:
    """Return the closing price N business days after reference_date.

    Downloads 90 days of history to find the target date.

    Args:
        symbol: Ticker symbol.
        reference_date: The recommendation date.
        n_days: Number of business days to look forward.

    Returns:
        float or None if data not available yet.
    """
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="3mo", auto_adjust=True)
    if hist.empty:
        return None

    ref = reference_date
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)

    # Filter trading days after the reference date
    hist.index = hist.index.tz_localize("UTC") if hist.index.tzinfo is None else hist.index.tz_convert("UTC")
    future = hist[hist.index > ref]
    if len(future) < n_days:
        return None

    return float(future.iloc[n_days - 1]["Close"])


def _evaluate_recommendation(recommendation: str, price_entry: float, price_exit: float) -> str:
    """Determine if a recommendation was correct.

    Args:
        recommendation: 'comprar', 'vender', or 'mantener'.
        price_entry: Price at recommendation.
        price_exit: Price at evaluation horizon.

    Returns:
        'acierto' or 'error'.
    """
    change_pct = (price_exit - price_entry) / price_entry
    rec = recommendation.lower().strip()

    if rec in ("comprar", "aumentar"):
        return "acierto" if change_pct > _THRESHOLDS["comprar"] else "error"
    if rec in ("vender", "reducir"):
        return "acierto" if change_pct < _THRESHOLDS["vender"] else "error"
    if rec == "mantener":
        return "acierto" if abs(change_pct) <= _THRESHOLDS["mantener"] else "error"
    return "error"


async def update_pending_recommendations() -> None:
    """Update price and result fields for all pending AI recommendations.

    Called daily by the scheduler. For each pending recommendation, attempts
    to fetch closing prices at 5, 10, and 20 business days and evaluates the
    result according to the recommendation type.
    """
    try:
        pending = await get_pending_ai_recommendations()
    except Exception as exc:
        logger.warning("update_pending_recommendations: no se pudieron obtener pendientes: %s", exc)
        return

    loop = asyncio.get_event_loop()

    for rec in pending:
        rec_id = rec["id"]
        symbol = rec["symbol"]
        recommendation = rec["recommendation"]
        price_entry = float(rec["price_at_recommendation"])
        recommended_at = rec["recommended_at"]

        updates = {}

        for n_days, price_field in _BUSINESS_DAYS_MAP.items():
            result_field = _RESULT_MAP[n_days]
            if rec.get(result_field) != "pendiente":
                continue  # already evaluated
            try:
                price = await loop.run_in_executor(
                    None, _get_price_on_business_day, symbol, recommended_at, n_days
                )
                if price is None:
                    continue  # not enough history yet
                result = _evaluate_recommendation(recommendation, price_entry, price)
                updates[price_field] = price
                updates[result_field] = result
            except Exception as exc:
                logger.warning("Error evaluando rec %d (%s) a %dd: %s", rec_id, symbol, n_days, exc)

        if updates:
            try:
                await update_ai_recommendation_result(
                    rec_id,
                    price_5d=updates.get("price_5d"),
                    price_10d=updates.get("price_10d"),
                    price_20d=updates.get("price_20d"),
                    result_5d=updates.get("result_5d"),
                    result_10d=updates.get("result_10d"),
                    result_20d=updates.get("result_20d"),
                )
                logger.info("Actualizada recomendación %d (%s): %s", rec_id, symbol, updates)
            except Exception as exc:
                logger.warning("Error guardando resultados para rec %d: %s", rec_id, exc)
