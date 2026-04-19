import asyncio
import re

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from config.settings import settings
from handlers.alerts import alerta_handler, borrar_alerta_handler, mis_alertas_handler
from handlers.commands import start, stock_cmd
from handlers.investment_profile import investment_profile_handler
from handlers.message import message_handler
from handlers.portfolio import rebalancear_handler
from interfaces.telegram.error_handler import global_error_handler
from interfaces.telegram.handlers.portfolio_handler import PortfolioHandler
from services.alert_checker import check_price_alerts


class TelegramBot:
    """Bootstrap del bot de Telegram."""

    def __init__(self, portfolio_handler: PortfolioHandler):
        self._portfolio_handler = portfolio_handler
        self._app = Application.builder().token(settings.telegram_token).build()

    async def run(self) -> None:
        portfolio_pattern = re.compile(
            r'^(\+|-|/cartera\b|/analiza\b|/plan_semana\b|analiza mi cartera|plan semanal|que deberia hacer esta semana|qué debería hacer esta semana|dame mi plan de cartera)',
            re.IGNORECASE,
        )

        self._app.add_error_handler(global_error_handler)
        self._app.add_handler(CommandHandler("start", start))
        self._app.add_handler(CommandHandler("stock", stock_cmd))

        self._app.add_handler(CommandHandler("alerta", alerta_handler))
        self._app.add_handler(CommandHandler("mis_alertas", mis_alertas_handler))
        self._app.add_handler(CommandHandler("borrar_alerta", borrar_alerta_handler))
        self._app.add_handler(CommandHandler("rebalancear", rebalancear_handler))

        self._app.add_handler(CommandHandler("cartera", self._portfolio_handler.handle))
        self._app.add_handler(CommandHandler("analiza", self._portfolio_handler.handle))
        self._app.add_handler(CommandHandler("plan_semana", self._portfolio_handler.handle))

        self._app.add_handler(CommandHandler("perfil", investment_profile_handler))
        self._app.add_handler(CommandHandler("perfil_inversion", investment_profile_handler))
        self._app.add_handler(CommandHandler("mi_perfil", investment_profile_handler))
        self._app.add_handler(CommandHandler("editar_perfil", investment_profile_handler))
        self._app.add_handler(CommandHandler("cancelar", investment_profile_handler))

        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, investment_profile_handler), group=0)
        self._app.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & filters.Regex(portfolio_pattern),
                self._portfolio_handler.handle,
            ),
            group=1,
        )
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler), group=1)

        job_queue = self._app.job_queue
        if job_queue:
            job_queue.run_repeating(check_price_alerts, interval=300, first=60)

        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            # Normal during debugger stop or process shutdown.
            pass

    async def shutdown(self) -> None:
        if self._app.updater and self._app.updater.running:
            await self._app.updater.stop()
        if self._app.running:
            await self._app.stop()
        await self._app.shutdown()
