import logging
from config import Config
from telegram.ext import Application, MessageHandler, filters
from handlers.message import message_handler

logging.basicConfig(level=Config.LOG_LEVEL)

def main():
    app = Application.builder().token(Config.TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    print("🤖 Bot iniciado - Polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
