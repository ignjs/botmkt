from telegram import Update
from telegram.ext import ContextTypes

from domain.exceptions import InvalidStrategyError
from services.ai_service import build_portfolio_builder_prompt, call_ai

VALID = {"growth", "valor", "dividendos", "momentum"}


async def portfolio_builder_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    parts = msg.text.strip().split(maxsplit=4)
    if len(parts) < 5:
        await msg.reply_text("Uso: /armar MONTO ESTRATEGIA HORIZONTE ACCIONES")
        return

    try:
        amount = float(parts[1])
        strategy = parts[2].lower()
        timeframe = parts[3]
        num_stocks = int(parts[4])
    except ValueError:
        await msg.reply_text("Formato inválido. Ejemplo: /armar 10000 growth 24m 8")
        return

    if strategy not in VALID:
        raise InvalidStrategyError()
    if num_stocks <= 0:
        await msg.reply_text("ACCIONES debe ser mayor a 0")
        return

    await msg.reply_text("⏳ Analizando propuesta de portafolio...")
    prompt = build_portfolio_builder_prompt(amount, strategy, timeframe, num_stocks)
    result = await call_ai(prompt)
    await msg.reply_text(result, parse_mode="Markdown")
