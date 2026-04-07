import re

from telegram import Update
from telegram.ext import ContextTypes

from db import add_position, get_investment_profile, remove_position
from services.perplexity import analyze_portfolio, analyze_stock
from services.planner import build_weekly_execution_plan
from services.portfolio_service import build_portfolio_snapshot, build_stock_analysis_context

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
        await msg.reply_text(f"📊 **Tu cartera** (Valor: ${snap['valor_total']:,.0f})\n{snap['tabla']}", parse_mode="Markdown")
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
            data, _, position = await build_stock_analysis_context(user_id, symbol)
            if not position:
                await msg.reply_text(
                    f"ℹ️ No tienes {symbol} guardado en cartera. Haré análisis solo con datos de mercado."
                )

            ia = await analyze_stock(symbol, data)
            await msg.reply_text(f"🎯 **Análisis IA {symbol}**:\n{ia}", parse_mode="Markdown")
        except Exception as e:
            await msg.reply_text(f"No pude analizar {symbol}: {str(e) if str(e) else 'No cotizando'}")
        return

    await msg.reply_text(DEFAULT_HELP_TEXT)
