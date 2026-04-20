from telegram import Update
from telegram.ext import ContextTypes

from services.ai_service import build_risk_prompt, call_ai


async def risk_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    parts = msg.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await msg.reply_text("Uso: /riesgo SYMBOL")
        return

    symbol = parts[1].upper()
    await msg.reply_text("⏳ Analizando riesgo...")
    result = await call_ai(build_risk_prompt(symbol))
    await msg.reply_text(f"⚠️ *Análisis de Riesgo — {symbol}*\n\n{result}", parse_mode="Markdown")
