class BotMKTError(Exception):
    """Base exception para errores de dominio."""


class InvalidSymbolError(BotMKTError):
    """Símbolo inválido o no soportado."""


class InvalidQuantityError(BotMKTError):
    """Cantidad inválida."""


class InvalidPriceError(BotMKTError):
    """Precio inválido."""


class PositionNotFoundError(BotMKTError):
    """Posición no encontrada."""


class ProfileNotFoundError(BotMKTError):
    """Perfil no encontrado."""


class MarketDataUnavailableError(BotMKTError):
    """No se pudieron obtener datos de mercado."""


class DatabaseError(BotMKTError):
    """Error de acceso a base de datos."""


class AIAnalysisError(BotMKTError):
    """Error al generar análisis con IA - timeout o respuesta inválida."""


class InvalidStrategyError(BotMKTError):
    """Estrategia de inversión no reconocida."""


class MissingReportTextError(BotMKTError):
    """El usuario no pegó el texto del earnings report."""
