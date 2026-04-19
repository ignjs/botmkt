from application.ports.position_repository_port import PositionRepositoryPort
from domain.entities.position import Position


class GetPortfolioUseCase:
    """Obtiene la cartera completa de un usuario."""

    def __init__(self, repo: PositionRepositoryPort):
        self._repo = repo

    async def execute(self, user_id: int) -> list[Position]:
        return await self._repo.find_all(user_id)
