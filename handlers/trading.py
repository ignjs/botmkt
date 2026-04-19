"""Handlers for broker commands: !comprar, !vender, /cuenta."""
import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import Config
from db import sync_order_to_positions

logger = logging.getLogger(__name__)

# Conversation state: pending_orders[user_id] = order_dict
_pending_orders: dict[int, dict] = {}
_CONFIRM_TIMEOUT_SECONDS = 60


async def comprar_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle !comprar SYMBOL quantity — initiate a buy order flow.

    Usage: !comprar AAPL 5

    Args:
        update: Telegram Update object.
        context: Telegram context.
    """
    msg = update.message
    user_id = update.effective_user.id
    text = msg.text.strip()

    parts = text.split()
    if len(parts) != 3:
        await msg.reply_text("Formato inválido. Usa: `!comprar AAPL 5`", parse_mode="Markdown")
        return

    symbol = parts[1].upper()
    try:
        qty = float(parts[2])
        if qty <= 0:
            raise ValueError
    except ValueError:
        await msg.reply_text("Cantidad inválida. Usa un número positivo.")
        return

    await _initiate_order(msg, user_id, symbol, qty, "buy")


async def vender_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle !vender SYMBOL quantity — initiate a sell order flow.

    Usage: !vender AAPL 5

    Args:
        update: Telegram Update object.
        context: Telegram context.
    """
    msg = update.message
    user_id = update.effective_user.id
    text = msg.text.strip()

    parts = text.split()
    if len(parts) != 3:
        await msg.reply_text("Formato inválido. Usa: `!vender AAPL 5`", parse_mode="Markdown")
        return

    symbol = parts[1].upper()
    try:
        qty = float(parts[2])
        if qty <= 0:
            raise ValueError
    except ValueError:
        await msg.reply_text("Cantidad inválida. Usa un número positivo.")
        return

    await _initiate_order(msg, user_id, symbol, qty, "sell")


async def _initiate_order(msg, user_id: int, symbol: str, qty: float, side: str) -> None:
    """Fetch estimated price and prompt the user for confirmation."""
    from services.broker_service import get_current_price_alpaca

    try:
        price = await get_current_price_alpaca(symbol)
    except Exception as exc:
        logger.warning("No se pudo obtener precio de %s: %s", symbol, exc)
        price = 0.0

    total_est = price * qty if price else 0.0
    side_label = "Comprar" if side == "buy" else "Vender"
    price_str = f"~${price:,.2f} c/u" if price else "precio de mercado"
    total_str = f" ≈ ${total_est:,.2f} total" if total_est else ""

    warning = ""
    if Config.ALPACA_MODE == "live":
        warning = "\n\n⚠️ *MODO REAL* — Esta operación usará dinero real."

    _pending_orders[user_id] = {"symbol": symbol, "qty": qty, "side": side}

    await msg.reply_text(
        f"⚠️ *Confirma:* {side_label} {qty} acciones de `{symbol}` a mercado "
        f"({price_str}{total_str}).\n"
        f"Responde *CONFIRMAR* para ejecutar.{warning}\n\n"
        f"_La orden se cancelará automáticamente en {_CONFIRM_TIMEOUT_SECONDS}s si no confirmas._",
        parse_mode="Markdown",
    )

    # Auto-cancel after timeout
    async def _auto_cancel():
        await asyncio.sleep(_CONFIRM_TIMEOUT_SECONDS)
        if user_id in _pending_orders:
            del _pending_orders[user_id]
            try:
                await msg.reply_text(f"⏰ Orden de {side_label.lower()} `{symbol}` cancelada por tiempo.")
            except Exception:
                pass

    asyncio.create_task(_auto_cancel())


async def confirmar_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle CONFIRMAR message to execute a pending order.

    Args:
        update: Telegram Update object.
        context: Telegram context.
    """
    msg = update.message
    user_id = update.effective_user.id

    if msg.text.strip().upper() != "CONFIRMAR":
        return

    pending = _pending_orders.pop(user_id, None)
    if not pending:
        return  # No pending order for this user

    symbol = pending["symbol"]
    qty = pending["qty"]
    side = pending["side"]
    side_label = "compra" if side == "buy" else "venta"

    try:
        from services.broker_service import place_order
        result = await place_order(symbol, qty, side)
        fill_price = result.get("filled_avg_price") or 0.0
        order_id = result.get("id", "?")

        fill_str = f"${fill_price:,.2f}" if fill_price else "precio de mercado"
        await msg.reply_text(
            f"✅ Orden de {side_label} ejecutada.\n"
            f"ID: `{order_id}`\nPrecio estimado: {fill_str}",
            parse_mode="Markdown",
        )

        # Sync to positions table
        if fill_price > 0:
            try:
                await sync_order_to_positions(user_id, symbol, qty, fill_price, side)
            except Exception as sync_exc:
                logger.warning("No se pudo sincronizar orden a positions: %s", sync_exc)

    except Exception as exc:
        logger.exception("Error ejecutando orden %s %s %s: %s", side, qty, symbol, exc)
        error_msg = str(exc)
        if "insufficient" in error_msg.lower():
            await msg.reply_text("❌ Fondos insuficientes para ejecutar la orden.")
        elif "not found" in error_msg.lower() or "invalid symbol" in error_msg.lower():
            await msg.reply_text(f"❌ Símbolo `{symbol}` no encontrado en Alpaca.")
        elif "market" in error_msg.lower() and "closed" in error_msg.lower():
            await msg.reply_text("❌ El mercado está cerrado en este momento.")
        else:
            await msg.reply_text(f"❌ No se pudo ejecutar la orden: {error_msg[:200]}")


async def cuenta_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cuenta command — show Alpaca account balance and open positions.

    Args:
        update: Telegram Update object.
        context: Telegram context.
    """
    msg = update.message

    try:
        from services.broker_service import get_account_info, get_open_positions
        account = await get_account_info()
        positions = await get_open_positions()

        mode_label = "📄 Paper Trading" if account["mode"] != "live" else "💵 MODO REAL"
        lines = [
            f"🏦 *Cuenta Alpaca* ({mode_label})\n",
            f"💰 Efectivo disponible: ${account['cash']:,.2f}",
            f"📊 Valor portafolio: ${account['portfolio_value']:,.2f}",
            f"💳 Poder de compra: ${account['buying_power']:,.2f}",
        ]

        if positions:
            lines.append(f"\n*Posiciones abiertas ({len(positions)}):*")
            for p in positions:
                pl_icon = "📈" if p["unrealized_pl"] >= 0 else "📉"
                lines.append(
                    f"{pl_icon} `{p['symbol']}` — {p['qty']:.0f} @ ${p['avg_entry_price']:,.2f} "
                    f"(actual: ${p['current_price']:,.2f} | P/L: ${p['unrealized_pl']:,.2f})"
                )
        else:
            lines.append("\nNo tienes posiciones abiertas en Alpaca.")

        await msg.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as exc:
        logger.exception("Error en cuenta_handler: %s", exc)
        await msg.reply_text(
            "❌ No pude obtener datos de la cuenta. "
            "Verifica que ALPACA_API_KEY y ALPACA_SECRET_KEY estén configuradas."
        )
