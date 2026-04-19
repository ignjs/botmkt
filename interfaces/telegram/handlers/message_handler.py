from telegram import Update
from telegram.ext import ContextTypes


class MessageHandlerAdapter:
    """Adaptador simple para mensajes generales."""

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("Usa /cartera, /perfil o +SYM qty price")
