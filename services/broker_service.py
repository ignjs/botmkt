"""Alpaca broker integration: place orders, get account info and open positions."""
import asyncio
import logging
from typing import Dict, List

from config import Config

logger = logging.getLogger(__name__)


def _get_alpaca_client():
    """Return an authenticated Alpaca REST client.

    Uses paper or live endpoint depending on ALPACA_MODE.

    Returns:
        alpaca_trade_api.REST: Authenticated client.

    Raises:
        ValueError: If API keys are not configured.
    """
    try:
        import alpaca_trade_api as tradeapi
    except ImportError as exc:
        raise ImportError("alpaca-trade-api not installed. Add it to requirements.txt.") from exc

    if not Config.ALPACA_API_KEY or not Config.ALPACA_SECRET_KEY:
        raise ValueError("ALPACA_API_KEY y ALPACA_SECRET_KEY deben estar configuradas.")

    base_url = (
        "https://paper-api.alpaca.markets"
        if Config.ALPACA_MODE != "live"
        else "https://api.alpaca.markets"
    )
    return tradeapi.REST(Config.ALPACA_API_KEY, Config.ALPACA_SECRET_KEY, base_url, api_version="v2")


async def place_order(
    symbol: str, qty: float, side: str, order_type: str = "market"
) -> Dict:
    """Submit an order to Alpaca.

    Args:
        symbol: Ticker symbol.
        qty: Number of shares (positive).
        side: 'buy' or 'sell'.
        order_type: Order type, default 'market'.

    Returns:
        dict with order details: id, symbol, qty, side, status, filled_avg_price.

    Raises:
        ValueError: If parameters are invalid.
        Exception: On Alpaca API failure.
    """
    if qty <= 0:
        raise ValueError("qty debe ser mayor a 0")
    if side not in ("buy", "sell"):
        raise ValueError("side debe ser 'buy' o 'sell'")

    loop = asyncio.get_event_loop()

    def _submit():
        api = _get_alpaca_client()
        order = api.submit_order(
            symbol=symbol,
            qty=qty,
            side=side,
            type=order_type,
            time_in_force="day",
        )
        return {
            "id": order.id,
            "symbol": order.symbol,
            "qty": float(order.qty),
            "side": order.side,
            "status": order.status,
            "filled_avg_price": float(order.filled_avg_price or 0),
        }

    return await loop.run_in_executor(None, _submit)


async def get_account_info() -> Dict:
    """Return Alpaca account balance information.

    Returns:
        dict with keys: cash, portfolio_value, buying_power, currency, mode.
    """
    loop = asyncio.get_event_loop()

    def _fetch():
        api = _get_alpaca_client()
        account = api.get_account()
        return {
            "cash": float(account.cash),
            "portfolio_value": float(account.portfolio_value),
            "buying_power": float(account.buying_power),
            "currency": account.currency,
            "mode": Config.ALPACA_MODE,
        }

    return await loop.run_in_executor(None, _fetch)


async def get_open_positions() -> List[Dict]:
    """Return a list of open positions in Alpaca.

    Returns:
        List of dicts with keys: symbol, qty, avg_entry_price, current_price,
        unrealized_pl, unrealized_plpc.
    """
    loop = asyncio.get_event_loop()

    def _fetch():
        api = _get_alpaca_client()
        positions = api.list_positions()
        return [
            {
                "symbol": p.symbol,
                "qty": float(p.qty),
                "avg_entry_price": float(p.avg_entry_price),
                "current_price": float(p.current_price),
                "unrealized_pl": float(p.unrealized_pl),
                "unrealized_plpc": float(p.unrealized_plpc),
            }
            for p in positions
        ]

    return await loop.run_in_executor(None, _fetch)


async def get_current_price_alpaca(symbol: str) -> float:
    """Return the latest trade price for a symbol from Alpaca.

    Args:
        symbol: Ticker symbol.

    Returns:
        float: Latest trade price.
    """
    loop = asyncio.get_event_loop()

    def _fetch():
        api = _get_alpaca_client()
        trade = api.get_latest_trade(symbol)
        return float(trade.price)

    return await loop.run_in_executor(None, _fetch)
