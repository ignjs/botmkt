
from telegram import Update, Message
from telegram.ext import ContextTypes
from services.stock_analyzer import get_stock_data, get_stock_data_fallback
from services.perplexity import analyze_stock
import datetime

# Mapeo de keywords a símbolos
KEYWORD_SYMBOLS = {
    "IAM": "IAM.SN",
    "IPSA": "^IPSA",
    "DÓLAR": "USDCLP=X",
    "DOLAR": "USDCLP=X",
    "USD": "USDCLP=X",
}

# Emojis para tabla
EMOJIS = {
    "compra": "🟢",
    "venta": "🔴",
    "spread": "➖",
    "vol": "💸",
}

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg: Message = update.message
    # 1. Solo texto
    if not msg.text:
        await msg.reply_text("⚠️ Solo se aceptan mensajes de texto con el símbolo bursátil (ej: IAM.SN, IPSA, dólar). No envíes imágenes, archivos ni GIFs.")
        return

    text_raw = msg.text.strip()
    text = text_raw.upper()
    # 2. Mensaje vacío o muy corto
    if not text or len(text) < 2:
        await msg.reply_text("Por favor, envía el símbolo bursátil (ej: IAM.SN, IPSA, dólar).")
        return

    # 3. Validar símbolo (solo letras, números, punto, guion, igual, ^)
    import re
    if not re.match(r'^[A-Z0-9\.\-=^]{2,}$', text) and text not in KEYWORD_SYMBOLS:
        await msg.reply_text("Símbolo inválido. Ejemplo válido: IAM.SN, IPSA, dólar.")
        return

    symbol = KEYWORD_SYMBOLS.get(text, text)
    timestamp = datetime.datetime.now().strftime("%H:%M")
    fuente = "BrainData"  # Default, cambiar según fallback

    try:
        try:
            data = await get_stock_data(symbol)
        except Exception:
            data = await get_stock_data_fallback(symbol)
            fuente = "Alpha"
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
        ia = await analyze_stock(symbol, data)
        await msg.reply_text(f"{tabla}\n**IA:** {ia}", parse_mode="Markdown")
    except Exception as e:
        await msg.reply_text(f"❌ Error: {str(e) if str(e) else 'No cotizando'}")
