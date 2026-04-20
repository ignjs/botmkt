from telegram import Update
from telegram.ext import ContextTypes

from services.ai_service import build_compare_prompt, call_ai

VALID = {"growth", "valor", "income"}


async def compare_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    parts = msg.text.strip().split(maxsplit=4)
    if len(parts) < 5:
        await msg.reply_text("Uso: /comparar SYMBOL_A SYMBOL_B TIPO HORIZONTE")
        return

    symbol_a, symbol_b = parts[1].upper(), parts[2].upper()
    investor_type = parts[3].lower()
    timeframe = parts[4]
    if investor_type not in VALID:
        await msg.reply_text("TIPO inválido. Usa: growth, valor o income.")
        return

    await msg.reply_text("⏳ Analizando comparación...")
    prompt = build_compare_prompt(symbol_a, symbol_b, investor_type, timeframe)
    result = await call_ai(prompt)
    await msg.reply_text(
        f"⚖️ *{symbol_a} vs {symbol_b} — {investor_type} / {timeframe}*\n\n{result}",
        parse_mode="Markdown",
    )
