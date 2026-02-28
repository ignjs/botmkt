import logging
from src.config import Config
from telegram.ext import Application, CommandHandler
from src.handlers import start, stock_cmd

logging.basicConfig(level=Config.LOG_LEVEL)

def main():
    app = Application.builder().token(Config.TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stock", stock_cmd))
    
    print("🤖 Bot iniciado - Polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
