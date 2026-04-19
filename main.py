import logging
import re

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from config import Config
from db import ensure_schema, init_pool
from handlers.ai_history import historial_ia_handler
from handlers.alerts import alerta_handler, alertas_enviadas_handler, borrar_alerta_handler, mis_alertas_handler
from handlers.investment_profile import investment_profile_handler
from handlers.message import message_handler
from handlers.metrics import metricas_handler
from handlers.portfolio import portfolio_handler
from handlers.trading import comprar_handler, confirmar_handler, cuenta_handler, vender_handler
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

    # Alert commands
    app.add_handler(CommandHandler("alerta", alerta_handler))
    app.add_handler(CommandHandler("mis_alertas", mis_alertas_handler))
    app.add_handler(CommandHandler("borrar_alerta", borrar_alerta_handler))
    app.add_handler(CommandHandler("alertas", alertas_enviadas_handler))

    # Register /rebalancear command
    from handlers.portfolio import rebalancear_handler
    app.add_handler(CommandHandler("rebalancear", rebalancear_handler))

    # Metrics command (E3)
    app.add_handler(CommandHandler("metricas", metricas_handler))

    # AI history command (E4)
    app.add_handler(CommandHandler("historial_ia", historial_ia_handler))

    # Broker commands (E5)
    app.add_handler(CommandHandler("cuenta", cuenta_handler))

    # Keep profile flow after explicit commands so slash commands are not intercepted.
    app.add_handler(MessageHandler(filters.TEXT, investment_profile_handler), group=0)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(portfolio_pattern), portfolio_handler), group=1)

    # Broker message handlers for !comprar, !vender and CONFIRMAR (E5)
    app.add_handler(
        MessageHandler(filters.TEXT & filters.Regex(re.compile(r'^!comprar\b', re.IGNORECASE)), comprar_handler),
        group=1,
    )
    app.add_handler(
        MessageHandler(filters.TEXT & filters.Regex(re.compile(r'^!vender\b', re.IGNORECASE)), vender_handler),
        group=1,
    )
    app.add_handler(
        MessageHandler(filters.TEXT & filters.Regex(re.compile(r'^CONFIRMAR$', re.IGNORECASE)), confirmar_handler),
        group=1,
    )

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler), group=1)

    # Schedule existing alert checker every 5 minutes
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(check_price_alerts, interval=300, first=60)

    # Start APScheduler (E2 + E4)
    try:
        from services.scheduler import start_scheduler
        start_scheduler(app.bot)
    except Exception as sched_exc:
        logging.warning("No se pudo iniciar el scheduler: %s", sched_exc)

    print("🤖 Bot iniciado - Polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
