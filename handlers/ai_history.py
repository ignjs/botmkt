import logging

from telegram import Update
from telegram.ext import ContextTypes

from db import get_ai_hit_rate_summary, get_recent_ai_recommendations

logger = logging.getLogger(__name__)


def _fmt_result(value: str, price: float | None, entry: float) -> str:
    if value == "pendiente" or price is None:
        return "⏳ --"
    pct = ((price - entry) / entry) * 100 if entry else 0
    icon = "✅" if value == "acierto" else "❌"
    return f"{icon} {pct:+.1f}%"


async def historial_ia_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    user_id = update.effective_user.id

    try:
        await msg.reply_text("⏳ Consultando historial de recomendaciones IA...")
        rows = await get_recent_ai_recommendations(user_id, limit=10)
        summary = await get_ai_hit_rate_summary(user_id)

        if not rows:
            await msg.reply_text("Aún no hay recomendaciones IA registradas.")
            return

        lines = [
            "🤖 *Historial de Recomendaciones IA*",
            f"Hit rate global: {summary['hit_rate_pct']:.1f}% "
            f"({summary['correct']}/{summary['total']} correctas)",
            "",
            "| Símbolo | Rec. | Precio | 5d | 10d |",
            "|---|---|---:|---|---|",
        ]

        for row in rows:
            entry = float(row["price_at_recommendation"])
            r5 = _fmt_result(row["result_5d"], float(row["price_5d"]) if row["price_5d"] else None, entry)
            r10 = _fmt_result(row["result_10d"], float(row["price_10d"]) if row["price_10d"] else None, entry)
            lines.append(
                f"| {row['symbol']} | {row['recommendation'].capitalize()} | ${entry:,.2f} | {r5} | {r10} |"
            )

        await msg.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as exc:
        logger.exception("Error en historial_ia_handler: %s", exc)
        await msg.reply_text("❌ No pude obtener el historial IA en este momento.")
