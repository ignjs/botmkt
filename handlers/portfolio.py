import logging
import re

from telegram import Update
from telegram.ext import ContextTypes

from db import add_position, get_investment_profile, remove_position, save_risk_snapshot
from services.ai_service import analyze_full_and_track_stock
from services.backtester import run_backtest
from services.optimizer import formatear_rebalanceo_para_telegram, optimizar_cartera
from services.perplexity import analyze_portfolio
from services.planner import build_weekly_execution_plan
from services.portfolio_service import build_portfolio_snapshot, build_stock_analysis_context
from services.risk_engine import calcular_metricas_cartera, formatear_metricas_para_telegram
from utils.rate_limiter import ai_limiter

logger = logging.getLogger(__name__)

SYMBOL_PATTERN = re.compile(r'^(\^[A-Z0-9]{2,}|[A-Z0-9]+(?:\.[A-Z]{1,5})?|[A-Z0-9]+=[A-Z])$')
PLAN_TRIGGERS = {
    "plan semanal",
    "que deberia hacer esta semana",
    "qué debería hacer esta semana",
    "dame mi plan de cartera",
}
ANALYZE_PORTFOLIO_TARGETS = {"esto", "cartera", "mi cartera", "cartera completa"}
DEFAULT_HELP_TEXT = (
    "Comando no reconocido. Usa +AAPL 10 170, -AAPL, /cartera, /analiza, /perfil o /plan_semana."
)


def _is_weekly_plan_request(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized.startswith("/plan_semana") or normalized in PLAN_TRIGGERS


async def portfolio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user_id = update.effective_user.id
    text = msg.text.strip()
    normalized = text.lower()

    if text.startswith('+'):
        try:
            parts = text[1:].strip().split()
            if len(parts) != 3:
                raise ValueError("Formato inválido")

            symbol, qty, price = parts
            symbol = symbol.upper()
            if not SYMBOL_PATTERN.match(symbol):
                await msg.reply_text("Símbolo inválido. Ejemplos válidos: IAM.SN, ^IPSA, USDCLP=X")
                return

            qty_value = float(qty)
            price_value = float(price)
            if qty_value <= 0 or price_value <= 0:
                raise ValueError("Cantidad y precio deben ser mayores a 0")

            await add_position(user_id, symbol, qty_value, price_value)
            await msg.reply_text(f"✅ {symbol} agregado ({qty_value:,.2f} @ {price_value:,.2f})")
        except ValueError:
            await msg.reply_text("Formato inválido. Usa: +AAPL 10 170")
        except Exception:
            await msg.reply_text("No pude guardar la posición en este momento. Intenta nuevamente.")
        return

    if text.startswith('-'):
        try:
            symbol = text[1:].strip().upper()
            if not symbol:
                raise ValueError("Formato inválido")
            if not SYMBOL_PATTERN.match(symbol):
                await msg.reply_text("Símbolo inválido. Ejemplos válidos: IAM.SN, ^IPSA, USDCLP=X")
                return

            await remove_position(user_id, symbol)
            await msg.reply_text(f"✅ {symbol} eliminado de tu cartera")
        except ValueError:
            await msg.reply_text("Formato inválido. Usa: -AAPL")
        except Exception:
            await msg.reply_text("Formato inválido. Usa: -AAPL")
        return

    if text == '/cartera':
        snap = await build_portfolio_snapshot(user_id)
        if not snap["detalle"]:
            await msg.reply_text("No tienes posiciones en tu cartera todavía.")
            return

        texto = f"📊 **Tu cartera** (Valor: ${snap['valor_total']:,.0f})\n{snap['tabla']}"

        # Add risk metrics section
        try:
            metricas = await calcular_metricas_cartera(snap["detalle"])
            texto += f"\n\n{formatear_metricas_para_telegram(metricas)}"
            # Persist snapshot (non-blocking on failure)
            try:
                await save_risk_snapshot(user_id, metricas)
            except Exception:
                pass
        except Exception:
            pass  # Risk metrics failure should not block portfolio display

        await msg.reply_text(texto, parse_mode="Markdown")
        return

    if _is_weekly_plan_request(text):
        profile = await get_investment_profile(user_id)
        if not profile:
            await msg.reply_text(
                "Primero define tu perfil con `/perfil`. Sin eso, el plan no puede evaluar disciplina ni límites reales.",
                parse_mode="Markdown",
            )
            return

        result = await build_weekly_execution_plan(user_id)
        await msg.reply_text(result["plan_markdown"], parse_mode="Markdown")
        return

    if normalized.startswith('/analiza'):
        allowed, retry_after = ai_limiter.is_allowed(user_id)
        if not allowed:
            await msg.reply_text(
                f"⏳ Demasiadas solicitudes al análisis IA. Espera {retry_after} segundos e intenta de nuevo."
            )
            return

        target = text[8:].strip()
        target_lower = target.lower()
        analizar_cartera_completa = target == "" or target_lower in ANALYZE_PORTFOLIO_TARGETS

        if analizar_cartera_completa:
            snap = await build_portfolio_snapshot(user_id)
            if not snap["detalle"]:
                await msg.reply_text("No tienes posiciones en tu cartera.")
                return

            ia = await analyze_portfolio(snap["tabla"])
            await msg.reply_text(f"🎯 **Análisis IA cartera**:\n{ia}", parse_mode="Markdown")
            return

        symbol = target.upper()
        if not SYMBOL_PATTERN.match(symbol):
            await msg.reply_text("Símbolo inválido. Ejemplos válidos: IAM.SN, ^IPSA, USDCLP=X")
            return

        try:
            await msg.reply_text("⏳ Analizando...")
            data, _, position = await build_stock_analysis_context(user_id, symbol)
            if not position:
                await msg.reply_text(
                    f"ℹ️ No tienes {symbol} guardado en cartera. Haré análisis solo con datos de mercado."
                )

            backtest = await run_backtest(symbol)
            data["backtest_summary"] = backtest["summary"]
            await msg.reply_text(backtest["summary"], parse_mode="Markdown")

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
            await msg.reply_text(f"🎯 **Análisis IA {symbol}**:\n{ia}", parse_mode="Markdown")
        except Exception as e:
            await msg.reply_text(f"No pude analizar {symbol}: {str(e) if str(e) else 'No cotizando'}")
        return

    await msg.reply_text(DEFAULT_HELP_TEXT)


async def rebalancear_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /rebalancear command - show optimal portfolio weights.

    Args:
        update: Telegram Update object.
        context: Telegram context.

    Returns:
        None
    """
    msg = update.message
    user_id = update.effective_user.id

    try:
        snap = await build_portfolio_snapshot(user_id)
        if not snap["detalle"] or len(snap["detalle"]) < 2:
            await msg.reply_text(
                "Necesitas al menos 2 posiciones en tu cartera para optimizar. "
                "Agrega posiciones con `+SYM cantidad precio`.",
                parse_mode="Markdown",
            )
            return

        profile = await get_investment_profile(user_id)
        if not profile:
            profile = {"risk_tolerance": 5, "max_position_pct": 25}

        await msg.reply_text("⚙️ Calculando pesos óptimos de Markowitz...")

        resultado = await optimizar_cartera(snap["detalle"], profile)
        texto = formatear_rebalanceo_para_telegram(resultado)
        await msg.reply_text(texto, parse_mode="Markdown")
    except Exception as e:
        logger.exception("Error en rebalancear_handler: %s", e)
        await msg.reply_text(f"❌ No pude calcular el rebalanceo: {str(e)}")

