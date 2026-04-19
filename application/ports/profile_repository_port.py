from abc import ABC, abstractmethod

from domain.entities.investment_profile import InvestmentProfile


class ProfileRepositoryPort(ABC):
    """Port de persistencia de perfiles de inversión."""

    @abstractmethod
    async def save(self, user_id: int, profile: InvestmentProfile) -> None:
        ...

    @abstractmethod
    async def find(self, user_id: int) -> InvestmentProfile | None:
        ...
