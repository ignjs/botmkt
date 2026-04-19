from typing import Dict, Optional, Tuple

import yfinance as yf

from db import get_positions
from services.stock_analyzer import get_stock_data, get_stock_data_fallback


async def get_market_data_with_source(symbol: str) -> Tuple[Dict, str]:
    try:
        return await get_stock_data(symbol), "BrainData"
    except Exception:
        return await get_stock_data_fallback(symbol), "Alpha"


async def get_saved_position(telegram_user_id: int, symbol: str) -> Optional[Dict]:
    positions = await get_positions(telegram_user_id)
    return next((pos for pos in positions if pos["symbol"].upper() == symbol.upper()), None)


def attach_position_context(market_data: Dict, position: Optional[Dict]) -> Dict:
    data = dict(market_data)
    if not position:
        return data

    qty = float(position["quantity"])
    avg_buy = float(position["avg_buy_price"])
    precio_actual = float(data.get("precio_actual", avg_buy))
    invested_value = qty * avg_buy
    market_value = qty * precio_actual
    position_pl_abs = market_value - invested_value
    position_pl_pct = ((precio_actual - avg_buy) / avg_buy * 100) if avg_buy else 0

    data.update(
        {
            "position_qty": qty,
            "avg_buy_price": avg_buy,
            "invested_value": invested_value,
            "market_value": market_value,
            "position_pl_abs": position_pl_abs,
            "position_pl_pct": position_pl_pct,
        }
    )
    return data


async def build_stock_analysis_context(telegram_user_id: int, symbol: str) -> Tuple[Dict, str, Optional[Dict]]:
    market_data, source = await get_market_data_with_source(symbol)
    position = await get_saved_position(telegram_user_id, symbol)
    return attach_position_context(market_data, position), source, position


async def build_portfolio_snapshot(telegram_user_id: int) -> Dict:
    positions = await get_positions(telegram_user_id)
    if not positions:
        return {"tabla": "Sin posiciones", "valor_total": 0, "detalle": []}

    detalle = []
    valor_total = 0.0
    for pos in positions:
        symbol = pos["symbol"]
        qty = float(pos["quantity"])
        avg_buy = float(pos["avg_buy_price"])
        stop_loss = float(pos["stop_loss"]) if pos.get("stop_loss") is not None else None
        atr = float(pos["atr"]) if pos.get("atr") is not None else None
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d")
        precio = float(hist["Close"].iloc[-1]) if not hist.empty else avg_buy
        valor = qty * precio
        pl = ((precio - avg_buy) / avg_buy) * 100 if avg_buy else 0
        valor_total += valor
        detalle.append(
            {
                "symbol": symbol,
                "qty": qty,
                "precio": precio,
                "valor": valor,
                "pl": pl,
                "stop_loss": stop_loss,
                "atr": atr,
            }
        )

    tabla = "| Símbolo | Cant | Precio | Valor | P/L | Stop |\n"
    tabla += "|---|---|---|---|---|---|\n"
    for item in detalle:
        stop_str = "—"
        if item["stop_loss"] is not None:
            stop_pct = ((item["stop_loss"] - item["precio"]) / item["precio"]) * 100
            stop_str = f"${item['stop_loss']:,.2f} ({stop_pct:+.1f}%)"
        tabla += (
            f"| {item['symbol']} | {int(item['qty'])} | {item['precio']:.2f} | "
            f"{item['valor']:.0f} | {item['pl']:+.1f}% | {stop_str} |\n"
        )

    return {"tabla": tabla, "valor_total": valor_total, "detalle": detalle}
