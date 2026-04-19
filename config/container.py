from application.use_cases.add_position import AddPositionUseCase
from application.use_cases.get_portfolio import GetPortfolioUseCase
from application.use_cases.remove_position import RemovePositionUseCase
from infrastructure.database.pool import close_pool, get_pool
from infrastructure.database.position_repository import PostgresPositionRepository
from infrastructure.database.schema import ensure_schema
from interfaces.telegram.bot import TelegramBot
from interfaces.telegram.handlers.portfolio_handler import PortfolioHandler


class Container:
    """Composición de dependencias de la aplicación."""

    def __init__(self) -> None:
        self._position_repo = PostgresPositionRepository()

    @classmethod
    async def build(cls) -> "Container":
        container = cls()
        await get_pool()
        await ensure_schema()
        return container

    def telegram_bot(self) -> TelegramBot:
        add = AddPositionUseCase(self._position_repo)
        remove = RemovePositionUseCase(self._position_repo)
        get_portfolio = GetPortfolioUseCase(self._position_repo)
        portfolio_handler = PortfolioHandler(add, remove, get_portfolio)
        return TelegramBot(portfolio_handler)

    async def teardown(self) -> None:
        await close_pool()
