import logging

from telegram import Update
from telegram.ext import ContextTypes

from services.portfolio_metrics import calculate_portfolio_metrics, format_metrics_for_telegram

logger = logging.getLogger(__name__)


async def metricas_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user_id = update.effective_user.id

    try:
        metrics = await calculate_portfolio_metrics(user_id)
        await msg.reply_text(format_metrics_for_telegram(metrics), parse_mode="Markdown")
    except Exception as exc:
        logger.exception("Error en metricas_handler: %s", exc)
        await msg.reply_text("❌ No pude calcular las métricas ahora. Intenta nuevamente.")
