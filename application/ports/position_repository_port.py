from abc import ABC, abstractmethod

from domain.entities.position import Position
from domain.value_objects.symbol import Symbol


class PositionRepositoryPort(ABC):
    """Port de persistencia de posiciones."""

    @abstractmethod
    async def save(self, user_id: int, position: Position) -> None:
        ...

    @abstractmethod
    async def delete(self, user_id: int, symbol: Symbol) -> None:
        ...

    @abstractmethod
    async def find_by_symbol(self, user_id: int, symbol: Symbol) -> Position | None:
        ...

    @abstractmethod
    async def find_all(self, user_id: int) -> list[Position]:
        ...
