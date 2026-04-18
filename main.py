import logging
import re

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from config import Config
from db import ensure_schema, init_pool
from handlers.alerts import alerta_handler, borrar_alerta_handler, mis_alertas_handler
from handlers.investment_profile import investment_profile_handler
from handlers.message import message_handler
from handlers.portfolio import portfolio_handler
from services.alert_checker import check_price_alerts

logging.basicConfig(level=Config.LOG_LEVEL)


async def _post_init(_: Application):
    try:
        await init_pool()
    except Exception as exc:
        logging.warning("No se pudo inicializar el pool de BD al iniciar: %s", exc)


def main():
    app = Application.builder().token(Config.TELEGRAM_TOKEN).post_init(_post_init).build()

    portfolio_pattern = re.compile(
        r'^(\+|-|/cartera\b|/analiza\b|/plan_semana\b|analiza mi cartera|plan semanal|que deberia hacer esta semana|qué debería hacer esta semana|dame mi plan de cartera)',
        re.IGNORECASE,
    )

    app.add_handler(MessageHandler(filters.TEXT, investment_profile_handler), group=0)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(portfolio_pattern), portfolio_handler), group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler), group=1)

    # Alert commands
    app.add_handler(CommandHandler("alerta", alerta_handler))
    app.add_handler(CommandHandler("mis_alertas", mis_alertas_handler))
    app.add_handler(CommandHandler("borrar_alerta", borrar_alerta_handler))

    # Register /rebalancear command
    from handlers.portfolio import rebalancear_handler
    app.add_handler(CommandHandler("rebalancear", rebalancear_handler))

    # Schedule alert checker every 5 minutes
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(check_price_alerts, interval=300, first=60)

    print("🤖 Bot iniciado - Polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
