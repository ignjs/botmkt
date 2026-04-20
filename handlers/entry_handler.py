from telegram import Update
from telegram.ext import ContextTypes

from services.ai_service import build_entry_prompt, call_ai


async def entry_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    parts = msg.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await msg.reply_text("Uso: /entrada SYMBOL")
        return

    symbol = parts[1].upper()
    await msg.reply_text("⏳ Analizando timing de entrada...")
    result = await call_ai(build_entry_prompt(symbol))
    await msg.reply_text(f"⏱️ *Timing de Entrada — {symbol}*\n\n{result}", parse_mode="Markdown")
