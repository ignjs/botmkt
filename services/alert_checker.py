"""Background job that checks price alerts and sends Telegram notifications."""
import logging

from telegram.ext import ContextTypes

from db import get_all_active_alerts, mark_alert_triggered
from services.market_data import DataUnavailableError, get_price

logger = logging.getLogger(__name__)


async def check_price_alerts(context: ContextTypes.DEFAULT_TYPE) -> None:
    """JobQueue callback: check all active alerts and fire triggered ones.

    Groups unique symbols to minimise API calls. Sends a Telegram message to
    the alert owner when a condition is met.

    Args:
        context: Telegram context (provides bot for sending messages).

    Returns:
        None

    Raises:
        None — all errors are caught and logged.
    """
    try:
        alerts = await get_all_active_alerts()
        if not alerts:
            return

        # Group by symbol to fetch price once per symbol
        symbols = list({a["symbol"] for a in alerts})
        prices: dict[str, float] = {}
        for symbol in symbols:
            try:
                data = await get_price(symbol)
                prices[symbol] = float(data["precio_actual"])
            except (DataUnavailableError, Exception) as e:
                logger.warning("No se pudo obtener precio de %s: %s", symbol, e)

        for alert in alerts:
            symbol = alert["symbol"]
            if symbol not in prices:
                continue

            current_price = prices[symbol]
            target = float(alert["target_price"])
            condition = alert["condition"]

            triggered = (condition == "above" and current_price >= target) or \
                        (condition == "below" and current_price <= target)

            if triggered:
                try:
                    direction = "subió sobre" if condition == "above" else "bajó bajo"
                    message = (
                        f"🔔 *Alerta disparada!*\n"
                        f"`{symbol}` {direction} ${target:,.2f}\n"
                        f"Precio actual: ${current_price:,.2f}"
                    )
                    await context.bot.send_message(
                        chat_id=alert["telegram_user_id"],
                        text=message,
                        parse_mode="Markdown",
                    )
                    await mark_alert_triggered(alert["id"])
                    logger.info(
                        "Alerta #%s disparada para user %s", alert["id"], alert["telegram_user_id"]
                    )
                except Exception as e:
                    logger.exception("Error disparando alerta #%s: %s", alert["id"], e)
    except Exception as e:
        logger.exception("Error en check_price_alerts: %s", e)
