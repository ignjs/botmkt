from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config.settings import settings
from domain.exceptions import MissingReportTextError
from services.ai_service import build_earnings_prompt, call_ai

WAITING_REPORT = 1


async def _earnings_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    parts = msg.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await msg.reply_text("Uso: /earnings COMPANY")
        return ConversationHandler.END

    context.user_data["earnings_company"] = parts[1]
    await msg.reply_text(f"📋 Listo. Pega el texto del earnings report de {parts[1]} y lo analizo.")
    return WAITING_REPORT


async def _earnings_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    company = context.user_data.get("earnings_company", "la compañía")
    report_text = msg.text.strip()

    if not report_text:
        raise MissingReportTextError()

    await msg.reply_text("⏳ Analizando earnings...")
    prompt = build_earnings_prompt(company, report_text)
    result = await call_ai(prompt)
    await msg.reply_text(f"📊 *Earnings {company}*\n\n{result}", parse_mode="Markdown")
    context.user_data.pop("earnings_company", None)
    return ConversationHandler.END


async def _earnings_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update and update.message:
        await update.message.reply_text(
            "⌛ Se agotó el tiempo para pegar el reporte. Usa /earnings EMPRESA nuevamente."
        )
    context.user_data.pop("earnings_company", None)
    return ConversationHandler.END


async def _earnings_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("earnings_company", None)
    await update.message.reply_text("Operación /earnings cancelada.")
    return ConversationHandler.END


earnings_conversation_handler = ConversationHandler(
    entry_points=[CommandHandler("earnings", _earnings_start)],
    states={
        WAITING_REPORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, _earnings_receive)],
        ConversationHandler.TIMEOUT: [MessageHandler(filters.ALL, _earnings_timeout)],
    },
    fallbacks=[CommandHandler("cancelar", _earnings_cancel)],
    conversation_timeout=settings.earnings_wait_timeout,
    per_user=True,
    per_chat=True,
    per_message=False,
)
