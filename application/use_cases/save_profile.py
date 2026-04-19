from application.ports.profile_repository_port import ProfileRepositoryPort
from domain.entities.investment_profile import InvestmentProfile


class SaveProfileUseCase:
    """Guarda un perfil validado de inversión."""

    def __init__(self, repo: ProfileRepositoryPort):
        self._repo = repo

    async def execute(self, user_id: int, profile_data: dict) -> InvestmentProfile:
        profile = InvestmentProfile(**profile_data)
        await self._repo.save(user_id, profile)
        return profile
