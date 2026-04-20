from telegram import Update
from telegram.ext import ContextTypes

from domain.exceptions import InvalidStrategyError
from services.ai_service import build_screener_prompt, call_ai

VALID = {"growth", "valor", "dividendos", "momentum"}


async def screener_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    text = msg.text.strip().split(maxsplit=2)
    if len(text) < 3:
        await msg.reply_text("Uso: /screener STRATEGY MERCADO")
        return

    strategy = text[1].lower()
    market = text[2]
    if strategy not in VALID:
        raise InvalidStrategyError()

    await msg.reply_text("⏳ Analizando screener...")
    prompt = build_screener_prompt(strategy, market)
    result = await call_ai(prompt)
    await msg.reply_text(f"🔎 *Screener — {strategy.capitalize()} en {market}*\n\n{result}", parse_mode="Markdown")
