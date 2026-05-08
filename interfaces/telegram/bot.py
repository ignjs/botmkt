import asyncio
import re

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from config.settings import settings
from handlers.ai_history import historial_ia_handler
from handlers.alerts import alertas_handler, alerta_handler, borrar_alerta_handler, mis_alertas_handler
from handlers.compare_handler import compare_handler
from handlers.commands import start, stock_cmd
from handlers.earnings_handler import earnings_conversation_handler
from handlers.entry_handler import entry_handler
from handlers.investment_profile import investment_profile_handler
from handlers.metrics import metricas_handler
from handlers.message import message_handler
from handlers.portfolio_builder_handler import portfolio_builder_handler
from handlers.portfolio import rebalancear_handler
from handlers.risk_handler import risk_handler
from handlers.screener_handler import screener_handler
from handlers.trading import cuenta_handler, trading_intent_handler
from interfaces.telegram.error_handler import global_error_handler
from interfaces.telegram.handlers.portfolio_handler import PortfolioHandler
from services.alert_checker import check_price_alerts
from services.scheduler import scheduler_manager


class TelegramBot:
    """Bootstrap del bot de Telegram."""

    def __init__(self, portfolio_handler: PortfolioHandler):
        self._portfolio_handler = portfolio_handler
        self._app = Application.builder().token(settings.telegram_token).build()
        self._enable_scheduler = False
        self._handlers_registered = False
        self._initialized = False
        self._started = False
        self._scheduler_started = False

    def enable_scheduler(self) -> None:
        self._enable_scheduler = True

    def _register_handlers(self) -> None:
        if self._handlers_registered:
            return

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
        self._app.add_handler(CommandHandler("alertas", alertas_handler))
        self._app.add_handler(CommandHandler("rebalancear", rebalancear_handler))
        self._app.add_handler(CommandHandler("metricas", metricas_handler))
        self._app.add_handler(CommandHandler("historial_ia", historial_ia_handler))
        self._app.add_handler(CommandHandler("screener", screener_handler))
        self._app.add_handler(earnings_conversation_handler)
        self._app.add_handler(CommandHandler("riesgo", risk_handler))
        self._app.add_handler(CommandHandler("comparar", compare_handler))
        self._app.add_handler(CommandHandler("armar", portfolio_builder_handler))
        self._app.add_handler(CommandHandler("entrada", entry_handler))
        self._app.add_handler(CommandHandler("cuenta", cuenta_handler))

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
            MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r"^(!comprar|!vender)\b|^CONFIRMAR$"), trading_intent_handler),
            group=1,
        )
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

        self._handlers_registered = True

    async def start_webhook_mode(self) -> None:
        self._register_handlers()
        if not self._initialized:
            await self._app.initialize()
            self._initialized = True
        if not self._started:
            await self._app.start()
            self._started = True
        if self._enable_scheduler and not self._scheduler_started:
            scheduler_manager.start(self._app.bot)
            self._scheduler_started = True

    async def process_webhook_update(self, update) -> None:
        await self._app.process_update(update)

    async def run(self) -> None:
        await self.start_webhook_mode()
        # No polling, solo webhooks
        # El procesamiento de updates se hace vía Flask en main.py
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            pass

    async def shutdown(self) -> None:
        if self._scheduler_started:
            scheduler_manager.shutdown()
            self._scheduler_started = False
        if self._app.updater and self._app.updater.running:
            await self._app.updater.stop()
        if self._app.running:
            await self._app.stop()
            self._started = False
        await self._app.shutdown()
        self._initialized = False
