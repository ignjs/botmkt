"""Proactive alert engine: checks all positions every 15 minutes and sends alerts."""
import asyncio
import logging
from typing import Any

import yfinance as yf

from db import (
    get_all_users_with_positions,
    get_positions,
    record_alert_sent,
    was_alert_sent_recently,
)

logger = logging.getLogger(__name__)

_RSI_PERIOD = 14
_VOLUME_LOOKBACK = 20
_VOLUME_SIGMA = 2


def _compute_rsi(close_series) -> float:
    delta = close_series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    roll_up = up.rolling(_RSI_PERIOD).mean()
    roll_down = down.rolling(_RSI_PERIOD).mean()
    rs = roll_up / roll_down
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.dropna().iloc[-1])


def _compute_volume_zscore(hist) -> float:
    """Return how many sigmas the last volume deviates from the 20-day mean."""
    volumes = hist["Volume"].dropna()
    if len(volumes) < _VOLUME_LOOKBACK + 1:
        return 0.0
    recent = volumes.iloc[-1]
    window = volumes.iloc[-(1 + _VOLUME_LOOKBACK):-1]
    mean = window.mean()
    std = window.std()
    if std == 0:
        return 0.0
    return float((recent - mean) / std)


def _get_metrics_for_position(symbol: str) -> dict:
    """Download 30 days of data and compute price, RSI, and volume z-score."""
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="30d", auto_adjust=True)
    if hist.empty or len(hist) < _RSI_PERIOD + 1:
        return {}
    current_price = float(hist["Close"].iloc[-1])
    rsi = _compute_rsi(hist["Close"])
    vol_zscore = _compute_volume_zscore(hist)
    return {"price": current_price, "rsi": rsi, "vol_zscore": vol_zscore}


async def _get_metrics_async(symbol: str) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_metrics_for_position, symbol)


def _format_alert_message(symbol: str, alert_type: str, metrics: dict, position: dict) -> str:
    price = metrics.get("price", 0)
    if alert_type == "stop_loss":
        stop = float(position.get("stop_loss", 0))
        return (
            f"🚨 *Alerta BotMKT — {symbol}*\n"
            f"Tipo: Stop-Loss alcanzado\n"
            f"Precio actual: ${price:,.2f}\n"
            f"Stop configurado: ${stop:,.2f}\n"
            f"Acción sugerida: Revisar posición o ejecutar salida."
        )
    if alert_type == "rsi_oversold":
        rsi = metrics.get("rsi", 0)
        return (
            f"📉 *Alerta BotMKT — {symbol}*\n"
            f"Tipo: RSI Extremo (Sobreventa)\n"
            f"RSI actual: {rsi:.1f} (< 30)\n"
            f"Precio actual: ${price:,.2f}\n"
            f"Acción sugerida: Posible oportunidad de compra o señal de debilidad."
        )
    if alert_type == "rsi_overbought":
        rsi = metrics.get("rsi", 0)
        return (
            f"📈 *Alerta BotMKT — {symbol}*\n"
            f"Tipo: RSI Extremo (Sobrecompra)\n"
            f"RSI actual: {rsi:.1f} (> 70)\n"
            f"Precio actual: ${price:,.2f}\n"
            f"Acción sugerida: Considerar toma de ganancias."
        )
    if alert_type == "volume_spike":
        zscore = metrics.get("vol_zscore", 0)
        return (
            f"📊 *Alerta BotMKT — {symbol}*\n"
            f"Tipo: Volumen Anormal\n"
            f"Volumen actual: {zscore:.1f}σ sobre la media de 20 días\n"
            f"Precio actual: ${price:,.2f}\n"
            f"Acción sugerida: Movimiento institucional probable, atención."
        )
    return f"⚠️ *Alerta BotMKT — {symbol}*\nTipo: {alert_type}"


async def check_all_positions(bot: Any) -> None:
    """Check all users' active positions and send alerts for critical conditions.

    Conditions checked:
    1. Stop-loss reached: current price ≤ stop_loss.
    2. RSI < 30 (oversold) or RSI > 70 (overbought).
    3. Abnormal volume: z-score > VOLUME_SIGMA.

    Args:
        bot: The Telegram Bot instance.
    """
    try:
        users = await get_all_users_with_positions()
    except Exception as exc:
        logger.warning("check_all_positions: no se pudo obtener usuarios: %s", exc)
        return

    for user_row in users:
        telegram_user_id = user_row["telegram_user_id"]
        try:
            positions = await get_positions(telegram_user_id)
        except Exception as exc:
            logger.warning("check_all_positions: error obteniendo posiciones de %s: %s", telegram_user_id, exc)
            continue

        for pos in positions:
            symbol = pos["symbol"]
            try:
                metrics = await _get_metrics_async(symbol)
                if not metrics:
                    continue

                current_price = metrics["price"]
                rsi = metrics["rsi"]
                vol_zscore = metrics["vol_zscore"]

                # Check conditions
                alerts_to_send = []

                stop_loss = float(pos["stop_loss"]) if pos.get("stop_loss") is not None else None
                if stop_loss is not None and current_price <= stop_loss:
                    alerts_to_send.append("stop_loss")

                if rsi < 30:
                    alerts_to_send.append("rsi_oversold")
                elif rsi > 70:
                    alerts_to_send.append("rsi_overbought")

                if vol_zscore > _VOLUME_SIGMA:
                    alerts_to_send.append("volume_spike")

                for alert_type in alerts_to_send:
                    already_sent = await was_alert_sent_recently(telegram_user_id, symbol, alert_type)
                    if already_sent:
                        continue
                    message = _format_alert_message(symbol, alert_type, metrics, pos)
                    await bot.send_message(
                        chat_id=telegram_user_id,
                        text=message,
                        parse_mode="Markdown",
                    )
                    await record_alert_sent(telegram_user_id, symbol, alert_type)
                    logger.info("Alerta enviada: %s / %s / %s", telegram_user_id, symbol, alert_type)

            except Exception as exc:
                logger.warning("check_all_positions: error procesando %s para %s: %s", symbol, telegram_user_id, exc)
