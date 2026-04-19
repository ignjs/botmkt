from decimal import Decimal

import pytest

from domain.entities.position import Position
from domain.value_objects.money import Money
from domain.value_objects.symbol import Symbol


@pytest.mark.asyncio
@pytest.mark.integration
async def test_save_and_retrieve_position(db_pool):
    async with db_pool.acquire() as conn:
        await conn.execute("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, telegram_user_id BIGINT UNIQUE NOT NULL)")
        await conn.execute("CREATE TABLE IF NOT EXISTS positions (id SERIAL PRIMARY KEY, user_id INTEGER, symbol TEXT, quantity NUMERIC, avg_buy_price NUMERIC)")
    assert Position(Symbol("TSLA"), Decimal("5"), Money(Decimal("250"))).quantity == Decimal("5")
