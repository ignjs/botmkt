import asyncio
import logging
from typing import Dict, List

import pandas as pd
import yfinance as yf

from config.settings import settings
from db import (
    get_positions_for_alerting,
    record_sent_alert,
    was_alert_sent_recently,
)
from services.market_data import DataUnavailableError, get_price

logger = logging.getLogger(__name__)


def _compute_rsi(close: pd.Series, period: int = 14) -> float | None:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.dropna()
    if rsi.empty:
        return None
    return float(rsi.iloc[-1])


async def _fetch_symbol_technicals(symbol: str) -> Dict[str, float | None]:
    def _load() -> Dict[str, float | None]:
        hist = yf.Ticker(symbol).history(period="90d", interval="1d")
        if hist.empty:
            return {"rsi": None, "volume": None, "volume_mean": None, "volume_std": None}

        close = pd.to_numeric(hist.get("Close"), errors="coerce")
        volume = pd.to_numeric(hist.get("Volume"), errors="coerce")
        rsi = _compute_rsi(close, period=14)

        volume = volume.dropna()
        if volume.empty:
            return {"rsi": rsi, "volume": None, "volume_mean": None, "volume_std": None}

        last_volume = float(volume.iloc[-1])
        baseline = volume.tail(20)
        mean_20 = float(baseline.mean()) if not baseline.empty else None
        std_20 = float(baseline.std(ddof=0)) if not baseline.empty else None
        return {
            "rsi": rsi,
            "volume": last_volume,
            "volume_mean": mean_20,
            "volume_std": std_20,
        }

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _load)


def _build_alert_messages(symbol: str, current_price: float, position: Dict, technicals: Dict) -> List[Dict[str, str]]:
    alerts: List[Dict[str, str]] = []
    stop_loss = position.get("stop_loss")

    if stop_loss is not None and current_price <= float(stop_loss):
        alerts.append(
            {
                "alert_type": "stop_loss",
                "text": (
                    f"🚨 *Alerta BotMKT — {symbol}*\n"
                    "Tipo: Stop-Loss alcanzado\n"
                    f"Precio actual: ${current_price:,.2f}\n"
                    f"Stop configurado: ${float(stop_loss):,.2f}\n"
                    "Acción sugerida: Revisar posición o ejecutar salida."
                ),
            }
        )

    rsi_value = technicals.get("rsi")
    if rsi_value is not None and (rsi_value < 30 or rsi_value > 70):
        rsi_label = "sobreventa" if rsi_value < 30 else "sobrecompra"
        alerts.append(
            {
                "alert_type": "rsi_extremo",
                "text": (
                    f"🚨 *Alerta BotMKT — {symbol}*\n"
                    f"Tipo: RSI extremo ({rsi_label})\n"
                    f"RSI(14): {rsi_value:.1f}\n"
                    f"Precio actual: ${current_price:,.2f}\n"
                    "Acción sugerida: Evaluar momentum y gestión de riesgo."
                ),
            }
        )

    volume = technicals.get("volume")
    mean_20 = technicals.get("volume_mean")
    std_20 = technicals.get("volume_std")
    if all(v is not None for v in (volume, mean_20, std_20)):
        threshold = float(mean_20) + 2 * float(std_20)
        if float(volume) > threshold:
            alerts.append(
                {
                    "alert_type": "volumen_anormal",
                    "text": (
                        f"🚨 *Alerta BotMKT — {symbol}*\n"
                        "Tipo: Volumen anormal\n"
                        f"Volumen actual: {float(volume):,.0f}\n"
                        f"Umbral (20d + 2σ): {threshold:,.0f}\n"
                        "Acción sugerida: Revisar noticias/catalizadores del activo."
                    ),
                }
            )

    return alerts


async def check_all_positions(bot) -> None:
    """Evaluate proactive alert conditions and send telegram notifications."""
    try:
        positions = await get_positions_for_alerting()
        if not positions:
            return

        for position in positions:
            symbol = position["symbol"]
            user_id = int(position["user_id"])
            telegram_user_id = int(position["telegram_user_id"])

            try:
                price_data = await get_price(symbol)
                current_price = float(price_data["precio_actual"])
            except (DataUnavailableError, Exception) as exc:
                logger.warning("No se pudo obtener precio para %s: %s", symbol, exc)
                continue

            try:
                technicals = await _fetch_symbol_technicals(symbol)
            except Exception as exc:
                logger.warning("No se pudo obtener técnicos para %s: %s", symbol, exc)
                technicals = {"rsi": None, "volume": None, "volume_mean": None, "volume_std": None}

            alerts = _build_alert_messages(symbol, current_price, position, technicals)
            for alert in alerts:
                already_sent = await was_alert_sent_recently(
                    user_id,
                    symbol,
                    alert["alert_type"],
                    settings.alert_cooldown_hours,
                )
                if already_sent:
                    continue

                await bot.send_message(
                    chat_id=telegram_user_id,
                    text=alert["text"],
                    parse_mode="Markdown",
                )
                await record_sent_alert(user_id, symbol, alert["alert_type"])

    except Exception as exc:
        logger.exception("Error en check_all_positions: %s", exc)
