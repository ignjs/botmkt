from application.ports.profile_repository_port import ProfileRepositoryPort
from domain.entities.investment_profile import InvestmentProfile


class GetProfileUseCase:
    """Obtiene el perfil de inversión de un usuario."""

    def __init__(self, repo: ProfileRepositoryPort):
        self._repo = repo

    async def execute(self, user_id: int) -> InvestmentProfile | None:
        return await self._repo.find(user_id)
