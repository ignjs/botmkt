import logging
import re

from telegram.ext import Application, MessageHandler, filters

from config import Config
from db import ensure_schema
from handlers.investment_profile import investment_profile_handler
from handlers.message import message_handler
from handlers.portfolio import portfolio_handler

logging.basicConfig(level=Config.LOG_LEVEL)


async def _post_init(_: Application):
    try:
        await ensure_schema()
    except Exception as exc:
        logging.warning("No se pudo inicializar el schema de BD al iniciar: %s", exc)


def main():
    app = Application.builder().token(Config.TELEGRAM_TOKEN).post_init(_post_init).build()

    portfolio_pattern = re.compile(
        r'^(\+|-|/cartera\b|/analiza\b|/plan_semana\b|analiza mi cartera|plan semanal|que deberia hacer esta semana|qué debería hacer esta semana|dame mi plan de cartera)',
        re.IGNORECASE,
    )

    app.add_handler(MessageHandler(filters.TEXT, investment_profile_handler), group=0)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(portfolio_pattern), portfolio_handler), group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler), group=1)

    print("🤖 Bot iniciado - Polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
