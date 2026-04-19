from decimal import Decimal

from application.ports.position_repository_port import PositionRepositoryPort
from domain.entities.position import Position
from domain.value_objects.money import Money
from domain.value_objects.symbol import Symbol


class AddPositionUseCase:
    """Agrega una posición o promedia una existente."""

    def __init__(self, repo: PositionRepositoryPort):
        self._repo = repo

    async def execute(self, user_id: int, symbol_str: str, quantity: float, price: float) -> Position:
        symbol = Symbol(symbol_str)
        qty = Decimal(str(quantity))
        money = Money(Decimal(str(price)))

        existing = await self._repo.find_by_symbol(user_id, symbol)
        if existing:
            updated = existing.merge_with_new_purchase(qty, money)
            await self._repo.save(user_id, updated)
            return updated

        created = Position(symbol=symbol, quantity=qty, avg_buy_price=money)
        await self._repo.save(user_id, created)
        return created
