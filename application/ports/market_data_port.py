from abc import ABC, abstractmethod


class MarketDataPort(ABC):
    """Port para obtener cotizaciones de mercado."""

    @abstractmethod
    async def get_price(self, symbol: str) -> float:
        ...
