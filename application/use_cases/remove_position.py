from application.ports.position_repository_port import PositionRepositoryPort
from domain.value_objects.symbol import Symbol


class RemovePositionUseCase:
    """Elimina una posición por símbolo."""

    def __init__(self, repo: PositionRepositoryPort):
        self._repo = repo

    async def execute(self, user_id: int, symbol_str: str) -> None:
        await self._repo.delete(user_id, Symbol(symbol_str))
