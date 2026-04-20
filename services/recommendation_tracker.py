import asyncio
import logging
from datetime import datetime
from typing import Optional

import pandas as pd
import yfinance as yf

from db import get_pending_ai_recommendations, update_ai_recommendation_horizon

logger = logging.getLogger(__name__)
HORIZONS = (5, 10, 20)


def evaluate_recommendation_result(recommendation: str, pct_change: float) -> str:
    rec = recommendation.lower().strip()
    if rec in {"comprar", "aumentar"}:
        return "acierto" if pct_change > 2.0 else "error"
    if rec in {"vender", "reducir"}:
        return "acierto" if pct_change < -2.0 else "error"
    return "acierto" if -5.0 <= pct_change <= 5.0 else "error"


def _business_days_between(start_dt: datetime, end_dt: datetime) -> int:
    start_date = pd.Timestamp(start_dt).normalize()
    end_date = pd.Timestamp(end_dt).normalize()
    if end_date <= start_date:
        return 0
    return len(pd.bdate_range(start=start_date, end=end_date)) - 1


async def _price_near_horizon(symbol: str, target_date: datetime) -> Optional[float]:
    def _load() -> Optional[float]:
        start = pd.Timestamp(target_date).normalize() - pd.Timedelta(days=3)
        end = pd.Timestamp(target_date).normalize() + pd.Timedelta(days=4)
        hist = yf.Ticker(symbol).history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
        if hist.empty:
            return None
        return float(hist["Close"].iloc[0])

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _load)


async def update_pending_recommendations() -> None:
    now = datetime.utcnow()
    pending = await get_pending_ai_recommendations()

    for rec in pending:
        recommended_at = rec["recommended_at"]
        days_elapsed = _business_days_between(recommended_at, now)
        entry_price = float(rec["price_at_recommendation"])

        for horizon in HORIZONS:
            result_key = f"result_{horizon}d"
            if rec.get(result_key) != "pendiente" or days_elapsed < horizon:
                continue

            target_date = pd.bdate_range(start=pd.Timestamp(recommended_at), periods=horizon + 1)[-1].to_pydatetime()
            price = await _price_near_horizon(rec["symbol"], target_date)
            if price is None:
                continue

            pct_change = ((price - entry_price) / entry_price) * 100.0 if entry_price else 0.0
            result = evaluate_recommendation_result(rec["recommendation"], pct_change)
            await update_ai_recommendation_horizon(rec["id"], horizon, price, result)
