import yfinance as yf
from db import get_positions
from typing import Dict

async def build_portfolio_snapshot(telegram_user_id: int) -> Dict:
    positions = await get_positions(telegram_user_id)
    if not positions:
        return {"tabla": "Sin posiciones", "valor_total": 0, "detalle": []}
    detalle = []
    valor_total = 0
    for pos in positions:
        symbol = pos["symbol"]
        qty = float(pos["quantity"])
        avg_buy = float(pos["avg_buy_price"])
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d")
        precio = float(hist["Close"].iloc[-1]) if not hist.empty else avg_buy
        valor = qty * precio
        pl = ((precio - avg_buy) / avg_buy) * 100 if avg_buy else 0
        valor_total += valor
        detalle.append({
            "symbol": symbol,
            "qty": qty,
            "precio": precio,
            "valor": valor,
            "pl": pl
        })
    # Tabla markdown
    tabla = "| Símbolo | Cant | Precio | Valor | P/L |\n"
    tabla += "|---|---|---|---|---|\n"
    for d in detalle:
        tabla += f"| {d['symbol']} | {int(d['qty'])} | {d['precio']:.2f} | {d['valor']:.0f} | {d['pl']:+.1f}% |\n"
    return {"tabla": tabla, "valor_total": valor_total, "detalle": detalle}
