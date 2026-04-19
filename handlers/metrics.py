"""Handler for /metricas command — quantitative portfolio metrics dashboard."""
import logging

from telegram import Update
from telegram.ext import ContextTypes

from services.portfolio_metrics import compute_portfolio_metrics
from services.portfolio_service import build_portfolio_snapshot

logger = logging.getLogger(__name__)


def _fmt_sharpe(sharpe) -> str:
    if sharpe is None:
        return "N/A"
    icon = "✅" if sharpe > 1 else ("⚠️" if sharpe > 0 else "🔴")
    label = "> 1 = bueno" if sharpe > 1 else ("moderado" if sharpe >= 0 else "negativo")
    return f"{sharpe:.2f}  {icon} ({label})"


def _fmt_beta(beta) -> str:
    if beta is None:
        return "N/A"
    if beta < 0.8:
        label = "defensivo"
    elif beta < 1.2:
        label = "moderado"
    else:
        label = "agresivo"
    return f"{beta:.2f}  ({label})"


def _fmt_hhi(hhi) -> str:
    if hhi is None:
        return "N/A"
    if hhi > 0.25:
        icon = "⚠️"
        label = "portafolio concentrado"
    elif hhi < 0.10:
        icon = "✅"
        label = "bien diversificado"
    else:
        icon = "🟡"
        label = "moderadamente diversificado"
    return f"{hhi:.2f}  {icon} ({label})"


async def metricas_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /metricas command — display quantitative portfolio dashboard.

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
        if not snap["detalle"]:
            await msg.reply_text(
                "Tu cartera está vacía. Agrega posiciones con `+SYM cantidad precio`.",
                parse_mode="Markdown",
            )
            return

        await msg.reply_text("⚙️ Calculando métricas cuantitativas (últimos 90 días)...")

        metrics = await compute_portfolio_metrics(snap["detalle"])

        benchmark = metrics.get("benchmark_symbol", "^GSPC")
        dominant = metrics.get("dominant_symbol")
        dominant_pct = ""
        if dominant and dominant in metrics.get("weights", {}):
            dominant_pct = f" ({metrics['weights'][dominant] * 100:.0f}% del portafolio)"

        lines = [
            "📊 *Métricas de Portafolio* (últimos 90 días)\n",
            f"📈 Sharpe Ratio: {_fmt_sharpe(metrics.get('sharpe'))}",
            f"⚖️ Beta vs {benchmark}: {_fmt_beta(metrics.get('beta'))}",
            f"📉 Max Drawdown: {metrics.get('max_drawdown_pct', 0):.1f}%",
            f"🎯 Concentración (HHI): {_fmt_hhi(metrics.get('hhi'))}",
        ]

        if dominant:
            lines.append(f"\nPosición dominante: `{dominant}`{dominant_pct}")
            if metrics.get("hhi", 0) > 0.25:
                lines.append("Recomendación: Considerar diversificar para reducir riesgo idiosincrático.")

        if metrics.get("symbols_excluded"):
            excl = ", ".join(metrics["symbols_excluded"])
            lines.append(f"\n⚠️ Sin datos históricos para: {excl}")

        await msg.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.exception("Error en metricas_handler: %s", e)
        await msg.reply_text("❌ No pude calcular las métricas en este momento. Intenta nuevamente.")
