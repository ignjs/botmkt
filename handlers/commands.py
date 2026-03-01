from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from services.stock_analyzer import get_stock_data
from services.perplexity import analyze_stock

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Bot Financiero Perplexity\n/stock <símbolo>\nEj: /stock IAM.SN"
    )

async def stock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = "IAM.SN" if not context.args else context.args[0].upper()
    
    try:
        await update.message.reply_text(f"📈 Analizando {symbol}...")
        indicadores = await get_stock_data(symbol)
        analisis = await analyze_stock(symbol, indicadores)
        
        tabla = f"""**{symbol}**
| Precio | ${indicadores['precio_actual']}
| 24h | {indicadores['cambio_24h']}%
| 7d | {indicadores['cambio_7d']}%
| RSI | {indicadores['rsi']}
| MACD | {indicadores['macd']}
| Vol | {indicadores['volumen']:,}"""
        
        await update.message.reply_text(f"{tabla}\n\n**IA:**\n{analisis}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
