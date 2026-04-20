import asyncio
from typing import Dict, List

from config.settings import settings


def _build_client():
    from alpaca.trading.client import TradingClient

    paper = settings.alpaca_mode.lower() == "paper"
    return TradingClient(
        api_key=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
        paper=paper,
    )


async def place_order(symbol, qty, side, order_type="market") -> Dict:
    def _place():
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        client = _build_client()
        req = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide(side),
            time_in_force=TimeInForce.DAY,
        )
        order = client.submit_order(req)
        return {
            "id": str(order.id),
            "symbol": order.symbol,
            "qty": float(order.qty),
            "side": order.side.value,
            "status": order.status.value,
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
        positions = client.get_all_positions()
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
