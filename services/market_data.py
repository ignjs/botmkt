"""Market data service with cascading fallback: yfinance → Alpha Vantage → stale cache."""
import asyncio
import logging
import os
from typing import Optional

import aiohttp
import yfinance as yf

from utils.cache import price_cache

logger = logging.getLogger(__name__)

ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY")
_YFINANCE_TIMEOUT = 5  # seconds


class DataUnavailableError(Exception):
    """Raised when no data source can provide price data for a symbol."""


async def _fetch_yfinance(symbol: str) -> Optional[dict]:
    """Fetch price data from yfinance with a timeout.

    Args:
        symbol: Ticker symbol.

    Returns:
        Optional[dict]: Price dict or None on failure.

    Raises:
        asyncio.TimeoutError: If yfinance takes longer than _YFINANCE_TIMEOUT seconds.
    """
    try:
        loop = asyncio.get_event_loop()

        def _sync_fetch():
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1d", auto_adjust=True)
            if hist.empty:
                return None
            precio = float(hist["Close"].iloc[-1])
            return {"precio_actual": precio, "symbol": symbol, "source": "yfinance"}

        data = await asyncio.wait_for(
            loop.run_in_executor(None, _sync_fetch),
            timeout=_YFINANCE_TIMEOUT,
        )
        return data
    except asyncio.TimeoutError:
        logger.warning("yfinance timeout para %s", symbol)
        return None
    except Exception as e:
        logger.warning("yfinance error para %s: %s", symbol, e)
        return None


async def _fetch_alpha_vantage(symbol: str) -> Optional[dict]:
    """Fetch price data from Alpha Vantage.

    Args:
        symbol: Ticker symbol.

    Returns:
        Optional[dict]: Price dict or None if key not configured or request fails.

    Raises:
        None
    """
    if not ALPHA_VANTAGE_KEY:
        return None
    try:
        url = (
            f"https://www.alphavantage.co/query"
            f"?function=GLOBAL_QUOTE&symbol={symbol}&apikey={ALPHA_VANTAGE_KEY}"
        )
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                data = await resp.json()
        quote = data.get("Global Quote", {})
        if not quote:
            return None
        precio = float(quote.get("05. price", 0))
        if precio <= 0:
            return None
        return {"precio_actual": precio, "symbol": symbol, "source": "alpha_vantage"}
    except Exception as e:
        logger.warning("Alpha Vantage error para %s: %s", symbol, e)
        return None


async def get_price(symbol: str) -> dict:
    """Retrieve the latest price for a symbol using a cascading fallback strategy.

    Cascade order:
    1. yfinance (timeout 5s)
    2. Alpha Vantage (if ALPHA_VANTAGE_KEY is configured)
    3. Stale cache entry (even if expired, flagged with stale=True)

    Args:
        symbol: Ticker symbol.

    Returns:
        dict: Price data dict. May include 'stale': True if from stale cache.

    Raises:
        DataUnavailableError: If all sources fail and no cached data exists.
    """
    try:
        # 1. Check fresh cache first
        cached = price_cache.get(symbol)
        if cached is not None:
            value, is_stale = cached
            if not is_stale:
                return value

        # 2. Try yfinance
        data = await _fetch_yfinance(symbol)
        if data:
            price_cache.set(symbol, data)
            return data

        # 3. Try Alpha Vantage
        data = await _fetch_alpha_vantage(symbol)
        if data:
            price_cache.set(symbol, data)
            return data

        # 4. Return stale cache if available
        if cached is not None:
            value, _ = cached
            stale_data = dict(value)
            stale_data["stale"] = True
            logger.warning("Retornando datos obsoletos del caché para %s", symbol)
            return stale_data

        raise DataUnavailableError(f"No hay datos disponibles para {symbol}")
    except DataUnavailableError:
        raise
    except Exception as e:
        logger.exception("Error en get_price(%s): %s", symbol, e)
        raise
