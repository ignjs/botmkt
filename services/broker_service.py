import asyncio
from typing import Dict, List

from config.settings import settings


def _build_client():
    from alpaca_trade_api import REST

    base_url = "https://paper-api.alpaca.markets" if settings.alpaca_mode.lower() == "paper" else "https://api.alpaca.markets"
    return REST(
        key_id=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
        base_url=base_url,
        api_version="v2",
    )


async def place_order(symbol, qty, side, order_type="market") -> Dict:
    def _place():
        client = _build_client()
        order = client.submit_order(
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
            "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else None,
        }

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _place)


async def get_account_info() -> Dict:
    def _get():
        client = _build_client()
        account = client.get_account()
        return {
            "status": account.status,
            "equity": float(account.equity),
            "cash": float(account.cash),
            "buying_power": float(account.buying_power),
        }

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get)


async def get_open_positions() -> List[Dict]:
    def _get():
        client = _build_client()
        positions = client.list_positions()
        return [
            {
                "symbol": p.symbol,
                "qty": float(p.qty),
                "avg_entry_price": float(p.avg_entry_price),
                "market_value": float(p.market_value),
                "unrealized_pl": float(p.unrealized_pl),
            }
            for p in positions
        ]

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get)
