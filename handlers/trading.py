import logging
import time

from telegram import Update
from telegram.ext import ContextTypes

from config.settings import settings
from db import sync_broker_order
from services.broker_service import get_account_info, get_open_positions, place_order

logger = logging.getLogger(__name__)
PENDING_ORDER_KEY = "pending_order"
PENDING_TIMEOUT_SECONDS = 60


async def _clear_pending_order(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    if not job:
        return
    chat_id = job.chat_id
    user_data = context.application.user_data.get(chat_id, {})
    pending = user_data.pop(PENDING_ORDER_KEY, None)
    if pending:
        await context.bot.send_message(
            chat_id=chat_id,
            text="⌛ Confirmación expirada. La orden fue cancelada automáticamente.",
        )


async def trading_intent_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    text = msg.text.strip()

    if text.upper() == "CONFIRMAR":
        await confirm_order_handler(update, context)
        return

    parts = text.split()
    if len(parts) != 3 or parts[0] not in {"!comprar", "!vender"}:
        return

    try:
        side = "buy" if parts[0] == "!comprar" else "sell"
        symbol = parts[1].upper()
        qty = float(parts[2])
        if qty <= 0:
            raise ValueError
    except ValueError:
        await msg.reply_text("Formato inválido. Usa: !comprar AAPL 5 o !vender AAPL 5")
        return

    warning = ""
    if settings.alpaca_mode.lower() == "live":
        warning = "\n⚠️ *MODO LIVE*: esto podría ejecutar dinero real."

    approx_text = "a mercado"
    pending_order = {
        "symbol": symbol,
        "qty": qty,
        "side": side,
        "created_at": time.time(),
    }
    context.user_data[PENDING_ORDER_KEY] = pending_order

    if context.job_queue:
        context.job_queue.run_once(
            _clear_pending_order,
            when=PENDING_TIMEOUT_SECONDS,
            chat_id=update.effective_user.id,
            name=f"clear_order_{update.effective_user.id}",
        )

    verb = "Comprar" if side == "buy" else "Vender"
    await msg.reply_text(
        f"⚠️ Confirma: {verb} {qty:g} acciones de {symbol} {approx_text}. "
        "Responde CONFIRMAR para ejecutar."
        f"{warning}",
        parse_mode="Markdown",
    )


async def confirm_order_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    pending = context.user_data.get(PENDING_ORDER_KEY)
    if not pending:
        await msg.reply_text("No hay órdenes pendientes por confirmar.")
        return

    elapsed = time.time() - float(pending["created_at"])
    if elapsed > PENDING_TIMEOUT_SECONDS:
        context.user_data.pop(PENDING_ORDER_KEY, None)
        await msg.reply_text("⌛ La orden expiró y fue cancelada. Vuelve a intentarlo.")
        return

    symbol = pending["symbol"]
    qty = float(pending["qty"])
    side = pending["side"]

    try:
        await msg.reply_text("⏳ Ejecutando orden en Alpaca...")
        result = await place_order(symbol=symbol, qty=qty, side=side, order_type="market")
        fill_price = float(result.get("filled_avg_price") or 0)
        if fill_price > 0:
            await sync_broker_order(
                telegram_user_id=update.effective_user.id,
                symbol=symbol,
                qty=qty,
                side=side,
                price=fill_price,
            )

        context.user_data.pop(PENDING_ORDER_KEY, None)
        await msg.reply_text(
            f"✅ Orden ejecutada. ID: {result['id']}. "
            f"Precio estimado: ${fill_price:,.2f}" if fill_price else f"✅ Orden ejecutada. ID: {result['id']}."
        )
    except Exception as exc:
        context.user_data.pop(PENDING_ORDER_KEY, None)
        error_text = str(exc).lower()
        if "insufficient" in error_text or "buying power" in error_text:
            await msg.reply_text("❌ Fondos insuficientes para ejecutar la orden.")
        elif "not found" in error_text or "symbol" in error_text:
            await msg.reply_text("❌ Símbolo no encontrado en Alpaca.")
        elif "market" in error_text and "closed" in error_text:
            await msg.reply_text("❌ Mercado cerrado. Intenta durante horario de mercado.")
        else:
            await msg.reply_text("❌ No pude ejecutar la orden. Intenta nuevamente.")
        logger.exception("Error al ejecutar orden: %s", exc)


async def cuenta_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message

    try:
        await msg.reply_text("⏳ Consultando cuenta y posiciones en Alpaca...")
        account = await get_account_info()
        positions = await get_open_positions()

        lines = [
            "🏦 *Cuenta Alpaca*",
            f"Modo: {settings.alpaca_mode}",
            f"Equity: ${account['equity']:,.2f}",
            f"Cash: ${account['cash']:,.2f}",
            f"Buying Power: ${account['buying_power']:,.2f}",
            "",
            "*Posiciones abiertas:*",
        ]
        if not positions:
            lines.append("- Sin posiciones abiertas")
        else:
            for p in positions:
                lines.append(
                    f"- `{p['symbol']}` {p['qty']:.2f} @ ${p['avg_entry_price']:,.2f} "
                    f"(MV ${p['market_value']:,.2f}, P/L ${p['unrealized_pl']:,.2f})"
                )

        await msg.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as exc:
        logger.exception("Error en /cuenta: %s", exc)
        await msg.reply_text("❌ No pude obtener información de Alpaca en este momento.")
