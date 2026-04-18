import datetime
import re

import yfinance as yf
from telegram import Message, Update
from telegram.ext import ContextTypes

from services.perplexity import analyze_stock, analyze_stock_with_sentiment
from services.portfolio_service import get_market_data_with_source
from utils.rate_limiter import ai_limiter

KEYWORD_SYMBOLS = {
    "IAM": "IAM.SN",
    "IPSA": "^IPSA",
    "DÓLAR": "USDCLP=X",
    "DOLAR": "USDCLP=X",
    "USD": "USDCLP=X",
}
SYMBOL_REGEX = re.compile(r'^[A-Z0-9\.\-=^]{2,}$')
EMOJIS = {
    "compra": "🟢",
    "venta": "🔴",
    "spread": "➖",
    "vol": "💸",
}


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg: Message = update.message

    if context.user_data.get("investment_profile_flow"):
        return

    if not msg.text:
        await msg.reply_text("⚠️ Solo se aceptan mensajes de texto con el símbolo bursátil (ej: IAM.SN, IPSA, dólar). No envíes imágenes, archivos ni GIFs.")
        return

    text_raw = msg.text.strip()
    text = text_raw.upper()
    if not text or len(text) < 2:
        await msg.reply_text("Por favor, envía el símbolo bursátil (ej: IAM.SN, IPSA, dólar).")
        return

    if text in KEYWORD_SYMBOLS:
        symbol = KEYWORD_SYMBOLS[text]
    elif SYMBOL_REGEX.match(text):
        ticker = yf.Ticker(text)
        try:
            hist = ticker.history(period="1d")
            if hist.empty:
                await msg.reply_text("El símbolo no existe o no está cotizando. Ejemplo válido: IAM.SN, IPSA, dólar.")
                return
        except Exception:
            await msg.reply_text("El símbolo no existe o no está cotizando. Ejemplo válido: IAM.SN, IPSA, dólar.")
            return
        symbol = text
    else:
        await msg.reply_text("Símbolo inválido. Ejemplo válido: IAM.SN, IPSA, dólar.")
        return

    timestamp = datetime.datetime.now().strftime("%H:%M")

    try:
        data, fuente = await get_market_data_with_source(symbol)
        if not data:
            raise ValueError("No cotizando")

        compra = data.get("compra") or data.get("precio_actual")
        venta = data.get("venta") or (compra + (data.get("spread") or 0))
        spread = abs(venta - compra)
        vol = data.get("volumen", 0)
        rsi = data.get("rsi", "-")
        macd = data.get("macd", "-")

        tabla = f"""
📈 **{symbol}** ({fuente} {timestamp})
| Compra {EMOJIS['compra']} | Venta {EMOJIS['venta']} | Spread {EMOJIS['spread']} | Vol {EMOJIS['vol']} |
| ${compra:,} | ${venta:,} | ${spread:,} | {vol:,} |
| RSI | MACD |
| {rsi} | {macd} |
"""
        user_id = update.effective_user.id
        allowed, retry_after = ai_limiter.is_allowed(user_id)
        if not allowed:
            await msg.reply_text(
                f"{tabla}\n⏳ Análisis IA no disponible ahora mismo. Espera {retry_after}s.",
                parse_mode="Markdown",
            )
            return

        ia, sentiment_score = await analyze_stock_with_sentiment(symbol, data)
        sentiment_line = ""
        if sentiment_score is not None:
            if sentiment_score >= 7:
                s_emoji = "🟢"
            elif sentiment_score >= 4:
                s_emoji = "🟡"
            else:
                s_emoji = "🔴"
            sentiment_line = f"\n*Sentimiento:* {sentiment_score}/10 {s_emoji}"
        await msg.reply_text(f"{tabla}\n**IA:** {ia}{sentiment_line}", parse_mode="Markdown")
    except Exception as e:
        await msg.reply_text(f"❌ Error: {str(e) if str(e) else 'No cotizando'}")
