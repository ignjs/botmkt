"""Handler for /historial_ia command — AI recommendation history and hit rate."""
import logging

from telegram import Update
from telegram.ext import ContextTypes

from db import get_ai_hit_rate, get_user_ai_recommendations

logger = logging.getLogger(__name__)

_REC_EMOJI = {"comprar": "🟢", "vender": "🔴", "mantener": "🟡"}
_RESULT_EMOJI = {"acierto": "✅", "error": "❌", "pendiente": "⏳"}


def _fmt_result(result: str, price_nd: float | None) -> str:
    emoji = _RESULT_EMOJI.get(result, "?")
    if result == "pendiente" or price_nd is None:
        return f"{emoji} --"
    return f"{emoji}"


async def historial_ia_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /historial_ia — show last 10 AI recommendations and global hit rate.

    Args:
        update: Telegram Update object.
        context: Telegram context.

    Returns:
        None
    """
    msg = update.message
    user_id = update.effective_user.id

    try:
        recs = await get_user_ai_recommendations(user_id, limit=10)
        stats = await get_ai_hit_rate(user_id)

        if not recs:
            await msg.reply_text(
                "No tienes recomendaciones IA registradas todavía.\n"
                "Usa `/analiza AAPL` para generar una.",
                parse_mode="Markdown",
            )
            return

        hit_rate_line = (
            f"Hit rate global: {stats['hit_rate_pct']:.0f}% "
            f"({stats['correct']}/{stats['total']} correctas)"
            if stats["total"] > 0
            else "Hit rate global: Sin datos evaluados aún."
        )

        lines = [
            "🤖 *Historial de Recomendaciones IA*",
            hit_rate_line,
            "",
            "| Símbolo | Rec. | Precio | 5d | 10d |",
            "|---|---|---|---|---|",
        ]

        for rec in recs:
            sym = rec["symbol"]
            rec_label = rec["recommendation"].capitalize()
            rec_icon = _REC_EMOJI.get(rec["recommendation"], "")
            price = f"${float(rec['price_at_recommendation']):,.2f}"
            r5 = _fmt_result(rec["result_5d"], rec.get("price_5d"))
            r10 = _fmt_result(rec["result_10d"], rec.get("price_10d"))
            lines.append(f"| {sym} | {rec_icon} {rec_label} | {price} | {r5} | {r10} |")

        n = len(recs)
        lines.append(f"\n_Datos basados en {stats['total']} recomendaciones históricas. Mostrando últimas {n}._")

        await msg.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.exception("Error en historial_ia_handler: %s", e)
        await msg.reply_text("❌ No pude obtener el historial de IA. Intenta nuevamente.")
