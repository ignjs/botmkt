import logging
import re
from config import Config
from telegram.ext import Application, MessageHandler, filters
from handlers.message import message_handler
from handlers.portfolio import portfolio_handler

logging.basicConfig(level=Config.LOG_LEVEL)

def main():
    app = Application.builder().token(Config.TELEGRAM_TOKEN).build()
    # Handler de cartera: comandos +AAPL, -AAPL, /cartera, analiza mi cartera
    portfolio_pattern = re.compile(r'^(\+|-|/cartera|/analiza\b|analiza mi cartera)', re.IGNORECASE)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(portfolio_pattern), portfolio_handler))
    # Handler de análisis individual
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    print("🤖 Bot iniciado - Polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
