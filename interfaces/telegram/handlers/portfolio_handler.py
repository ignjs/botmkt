import re
from decimal import Decimal

from telegram import Update
from telegram.ext import ContextTypes

from application.use_cases.add_position import AddPositionUseCase
from application.use_cases.get_portfolio import GetPortfolioUseCase
from application.use_cases.remove_position import RemovePositionUseCase
from db import get_investment_profile, save_risk_snapshot
from services.ai_service import analyze_full_and_track_stock
from services.backtester import run_backtest
from services.perplexity import analyze_portfolio
from services.planner import build_weekly_execution_plan
from services.portfolio_service import build_portfolio_snapshot, build_stock_analysis_context
from services.risk_engine import calcular_metricas_cartera, formatear_metricas_para_telegram
from utils.rate_limiter import ai_limiter

SYMBOL_PATTERN = re.compile(r'^(\^[A-Z0-9]{2,}|[A-Z0-9]+(?:\.[A-Z]{1,5})?|[A-Z0-9]+=[A-Z])$')
ANALYZE_PORTFOLIO_TARGETS = {"", "esto", "cartera", "mi cartera", "cartera completa"}
PLAN_TRIGGERS = {
    "plan semanal",
    "que deberia hacer esta semana",
    "qué debería hacer esta semana",
    "dame mi plan de cartera",
}


class PortfolioHandler:
    """Handler de cartera sin lógica de infraestructura."""

    def __init__(
        self,
        add_position: AddPositionUseCase,
        remove_position: RemovePositionUseCase,
        get_portfolio: GetPortfolioUseCase,
    ):
        self._add = add_position
        self._remove = remove_position
        self._get = get_portfolio

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.message
        text = (message.text or "").strip()
        normalized = text.lower()
        user_id = update.effective_user.id

        if text.startswith("+"):
            parts = text[1:].strip().split()
            if len(parts) != 3:
                await message.reply_text("Formato inválido. Usa: +AAPL 10 170")
                return
            symbol, qty, price = parts
            if not SYMBOL_PATTERN.match(symbol.upper()):
                await message.reply_text("Símbolo inválido.")
                return
            result = await self._add.execute(user_id, symbol, float(qty), float(price))
            await message.reply_text(
                f"✅ {result.symbol} agregado ({Decimal(result.quantity):,.2f} @ {result.avg_buy_price.amount:,.2f})"
            )
            return

        if text.startswith("-"):
            symbol = text[1:].strip().upper()
            if not symbol:
                await message.reply_text("Formato inválido. Usa: -AAPL")
                return
            await self._remove.execute(user_id, symbol)
            await message.reply_text(f"✅ {symbol} eliminado de tu cartera")
            return

        if text == "/cartera":
            snap = await build_portfolio_snapshot(user_id)
            if not snap["detalle"]:
                await message.reply_text("No tienes posiciones en tu cartera todavía.")
                return

            texto = f"📊 **Tu cartera** (Valor: ${snap['valor_total']:,.0f})\n{snap['tabla']}"

            try:
                metricas = await calcular_metricas_cartera(snap["detalle"])
                texto += f"\n\n{formatear_metricas_para_telegram(metricas)}"
                try:
                    await save_risk_snapshot(user_id, metricas)
                except Exception:
                    pass
            except Exception:
                pass

            await message.reply_text(texto, parse_mode="Markdown")
            return

        if normalized.startswith("/plan_semana") or normalized in PLAN_TRIGGERS:
            profile = await get_investment_profile(user_id)
            if not profile:
                await message.reply_text(
                    "Primero define tu perfil con `/perfil`. Sin eso, el plan no puede evaluar disciplina ni límites reales.",
                    parse_mode="Markdown",
                )
                return

            result = await build_weekly_execution_plan(user_id)
            await message.reply_text(result["plan_markdown"], parse_mode="Markdown")
            return

        if normalized.startswith("/analiza"):
            allowed, retry_after = ai_limiter.is_allowed(user_id)
            if not allowed:
                await message.reply_text(
                    f"⏳ Demasiadas solicitudes al análisis IA. Espera {retry_after} segundos e intenta de nuevo."
                )
                return

            target = text[8:].strip()
            target_lower = target.lower()
            analizar_cartera_completa = target_lower in ANALYZE_PORTFOLIO_TARGETS

            if analizar_cartera_completa:
                snap = await build_portfolio_snapshot(user_id)
                if not snap["detalle"]:
                    await message.reply_text("No tienes posiciones en tu cartera.")
                    return

                ia = await analyze_portfolio(snap["tabla"])
                await message.reply_text(f"🎯 **Análisis IA cartera**:\n{ia}", parse_mode="Markdown")
                return

            symbol = target.upper()
            if not SYMBOL_PATTERN.match(symbol):
                await message.reply_text("Símbolo inválido. Ejemplos válidos: IAM.SN, ^IPSA, USDCLP=X")
                return

            try:
                data, _, position = await build_stock_analysis_context(user_id, symbol)
                if not position:
                    await message.reply_text(
                        f"ℹ️ No tienes {symbol} guardado en cartera. Haré análisis solo con datos de mercado."
                    )

                backtest = await run_backtest(symbol)
                data["backtest_summary"] = backtest["summary"]
                await message.reply_text(backtest["summary"], parse_mode="Markdown")

                extra_context = (
                    f"Precio actual: {data.get('precio_actual')}\n"
                    f"Cambio 24h: {data.get('cambio_24h')}\n"
                    f"RSI: {data.get('rsi')}\n"
                    f"MACD: {data.get('macd')}\n"
                    f"{backtest['summary']}"
                )
                ia = await analyze_full_and_track_stock(
                    user_id,
                    symbol,
                    float(data.get("precio_actual", 0) or 0),
                    extra_context=extra_context,
                )
                await message.reply_text(f"🎯 **Análisis IA {symbol}**:\n{ia}", parse_mode="Markdown")
            except Exception as e:
                await message.reply_text(f"No pude analizar {symbol}: {str(e) if str(e) else 'No cotizando'}")
            return

        await message.reply_text("Comando no reconocido para cartera.")
