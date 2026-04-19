from decimal import Decimal
from unittest.mock import AsyncMock

import asyncpg
import pytest

from domain.entities.position import Position
from domain.value_objects.money import Money
from domain.value_objects.symbol import Symbol


@pytest.fixture
def sample_position() -> Position:
    return Position(
        symbol=Symbol("AAPL"),
        quantity=Decimal("10"),
        avg_buy_price=Money(Decimal("210.00")),
    )


@pytest.fixture
def mock_position_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_symbol.return_value = None
    repo.find_all.return_value = []
    return repo


@pytest.fixture(scope="session")
async def db_pool():
    import os

    test_db_url = os.environ.get("TEST_DATABASE_URL")
    if not test_db_url:
        pytest.skip("TEST_DATABASE_URL no configurado")
    pool = await asyncpg.create_pool(test_db_url)
    yield pool
    await pool.close()
