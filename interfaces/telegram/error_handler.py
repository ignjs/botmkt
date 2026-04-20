import logging

from telegram.ext import ContextTypes

from domain.exceptions import (
    AIAnalysisError,
    DatabaseError,
    InvalidPriceError,
    InvalidQuantityError,
    InvalidStrategyError,
    InvalidSymbolError,
    MarketDataUnavailableError,
    MissingReportTextError,
    PositionNotFoundError,
)

logger = logging.getLogger(__name__)


async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Traductor global de excepciones a mensajes de usuario."""
    error = context.error
    if isinstance(error, InvalidSymbolError):
        msg = "❌ Símbolo no encontrado. Verifica el ticker (ej: AAPL, IAM.SN)"
    elif isinstance(error, InvalidQuantityError):
        msg = "❌ Cantidad inválida. Usa números positivos (ej: +AAPL 10 210)"
    elif isinstance(error, InvalidPriceError):
        msg = "❌ Precio inválido. El precio debe ser mayor a cero"
    elif isinstance(error, PositionNotFoundError):
        msg = "❌ No tienes esa posición en tu cartera"
    elif isinstance(error, MarketDataUnavailableError):
        msg = "⚠️ No se pudo obtener datos de mercado. Intenta en unos minutos"
    elif isinstance(error, DatabaseError):
        msg = "🔴 Error de base de datos. El equipo ha sido notificado"
    elif isinstance(error, AIAnalysisError):
        msg = "⚠️ El análisis tardó demasiado. Intenta nuevamente en un momento."
    elif isinstance(error, InvalidStrategyError):
        msg = "❌ Estrategia no válida. Usa: growth, valor, dividendos o momentum."
    elif isinstance(error, MissingReportTextError):
        msg = "❌ No recibí el texto del reporte. Usa /earnings EMPRESA y luego pega el texto."
    else:
        logger.exception("Error no manejado", exc_info=error)
        msg = "❌ Ocurrió un error inesperado. Intenta nuevamente"

    if update and hasattr(update, "message") and getattr(update, "message"):
        await update.message.reply_text(msg)
