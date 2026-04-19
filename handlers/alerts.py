"""Handlers for price alert commands: /alerta, /mis_alertas, /borrar_alerta, /alertas."""
import logging
import re

from telegram import Update
from telegram.ext import ContextTypes

from db import add_price_alert, delete_price_alert, get_alerts_sent_last_24h, get_user_alerts

logger = logging.getLogger(__name__)

ALERT_PATTERN = re.compile(
    r'^/alerta\s+([A-Z0-9\.=^-]+)\s+(above|below)\s+(\d+(?:\.\d+)?)$',
    re.IGNORECASE,
)


async def alerta_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /alerta command to create a price alert.

    Usage: /alerta AAPL above 200

    Args:
        update: Telegram Update object.
        context: Telegram context.

    Returns:
        None
    """
    msg = update.message
    user_id = update.effective_user.id
    text = msg.text.strip()

    match = ALERT_PATTERN.match(text)
    if not match:
        await msg.reply_text(
            "Formato inválido. Usa: `/alerta AAPL above 200` o `/alerta AAPL below 150`",
            parse_mode="Markdown",
        )
        return

    symbol = match.group(1).upper()
    condition = match.group(2).lower()
    target_price = float(match.group(3))

    try:
        alert_id = await add_price_alert(user_id, symbol, condition, target_price)
        condition_es = "sube de" if condition == "above" else "baja de"
        await msg.reply_text(
            f"✅ Alerta #{alert_id} creada: {symbol} cuando {condition_es} ${target_price:,.2f}",
        )
    except Exception as e:
        logger.exception("Error en alerta_handler: %s", e)
        await msg.reply_text("❌ No pude crear la alerta. Intenta nuevamente.")


async def mis_alertas_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /mis_alertas command to list active alerts.

    Args:
        update: Telegram Update object.
        context: Telegram context.

    Returns:
        None
    """
    msg = update.message
    user_id = update.effective_user.id

    try:
        alerts = await get_user_alerts(user_id)
        if not alerts:
            await msg.reply_text(
                "No tienes alertas activas. Crea una con `/alerta AAPL above 200`.",
                parse_mode="Markdown",
            )
            return

        lines = ["🔔 *Tus alertas activas:*\n"]
        for a in alerts:
            direction = "↑ sube de" if a["condition"] == "above" else "↓ baja de"
            lines.append(f"#{a['id']} `{a['symbol']}` {direction} ${float(a['target_price']):,.2f}")

        await msg.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.exception("Error en mis_alertas_handler: %s", e)
        await msg.reply_text("❌ No pude obtener tus alertas. Intenta nuevamente.")


async def borrar_alerta_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /borrar_alerta command to delete an alert by ID.

    Usage: /borrar_alerta 3

    Args:
        update: Telegram Update object.
        context: Telegram context.

    Returns:
        None
    """
    msg = update.message
    user_id = update.effective_user.id
    text = msg.text.strip()

    parts = text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await msg.reply_text("Formato inválido. Usa: `/borrar_alerta 3`", parse_mode="Markdown")
        return

    alert_id = int(parts[1])

    try:
        deleted = await delete_price_alert(user_id, alert_id)
        if deleted:
            await msg.reply_text(f"✅ Alerta #{alert_id} eliminada.")
        else:
            await msg.reply_text(f"⚠️ No encontré la alerta #{alert_id} o no te pertenece.")
    except Exception as e:
        logger.exception("Error en borrar_alerta_handler: %s", e)
        await msg.reply_text("❌ No pude eliminar la alerta. Intenta nuevamente.")


async def alertas_enviadas_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /alertas command — show alerts sent in the last 24 hours.

    Args:
        update: Telegram Update object.
        context: Telegram context.

    Returns:
        None
    """
    msg = update.message
    user_id = update.effective_user.id

    try:
        records = await get_alerts_sent_last_24h(user_id)
        if not records:
            await msg.reply_text("No recibiste alertas automáticas en las últimas 24 horas. ✅")
            return

        lines = ["🔔 *Alertas enviadas (últimas 24h):*\n"]
        _LABELS = {
            "stop_loss": "🛑 Stop-Loss alcanzado",
            "rsi_oversold": "📉 RSI Sobreventa (<30)",
            "rsi_overbought": "📈 RSI Sobrecompra (>70)",
            "volume_spike": "📊 Volumen Anormal",
        }
        for rec in records:
            label = _LABELS.get(rec["alert_type"], rec["alert_type"])
            ts = rec["sent_at"].strftime("%H:%M") if rec["sent_at"] else "—"
            lines.append(f"• `{rec['symbol']}` — {label} ({ts})")

        await msg.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.exception("Error en alertas_enviadas_handler: %s", e)
        await msg.reply_text("❌ No pude obtener el historial de alertas. Intenta nuevamente.")
