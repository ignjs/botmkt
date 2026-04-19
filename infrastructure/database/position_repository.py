from decimal import Decimal

from application.ports.position_repository_port import PositionRepositoryPort
from domain.entities.position import Position
from domain.value_objects.money import Money
from domain.value_objects.symbol import Symbol
from infrastructure.database.pool import get_pool


class PostgresPositionRepository(PositionRepositoryPort):
    """Repositorio PostgreSQL de posiciones."""

    async def _get_or_create_user_id(self, telegram_user_id: int) -> int:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM users WHERE telegram_user_id = $1", telegram_user_id
            )
            if row:
                return int(row["id"])
            created = await conn.fetchrow(
                "INSERT INTO users (telegram_user_id) VALUES ($1) RETURNING id", telegram_user_id
            )
            return int(created["id"])

    async def save(self, user_id: int, position: Position) -> None:
        db_user_id = await self._get_or_create_user_id(user_id)
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT quantity, avg_buy_price FROM positions WHERE user_id = $1 AND symbol = $2",
                db_user_id,
                str(position.symbol),
            )
            if row:
                existing = Position(
                    symbol=position.symbol,
                    quantity=Decimal(str(row["quantity"])),
                    avg_buy_price=Money(Decimal(str(row["avg_buy_price"]))),
                )
                merged = existing.merge_with_new_purchase(position.quantity, position.avg_buy_price)
                await conn.execute(
                    """
                    UPDATE positions
                    SET quantity = $1, avg_buy_price = $2, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $3 AND symbol = $4
                    """,
                    float(merged.quantity),
                    float(merged.avg_buy_price.amount),
                    db_user_id,
                    str(position.symbol),
                )
                return

            await conn.execute(
                """
                INSERT INTO positions (user_id, symbol, quantity, avg_buy_price)
                VALUES ($1, $2, $3, $4)
                """,
                db_user_id,
                str(position.symbol),
                float(position.quantity),
                float(position.avg_buy_price.amount),
            )

    async def delete(self, user_id: int, symbol: Symbol) -> None:
        db_user_id = await self._get_or_create_user_id(user_id)
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM positions WHERE user_id = $1 AND symbol = $2",
                db_user_id,
                str(symbol),
            )

    async def find_by_symbol(self, user_id: int, symbol: Symbol) -> Position | None:
        db_user_id = await self._get_or_create_user_id(user_id)
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT symbol, quantity, avg_buy_price FROM positions WHERE user_id = $1 AND symbol = $2",
                db_user_id,
                str(symbol),
            )
            if row is None:
                return None
            return Position(
                symbol=Symbol(str(row["symbol"])),
                quantity=Decimal(str(row["quantity"])),
                avg_buy_price=Money(Decimal(str(row["avg_buy_price"]))),
            )

    async def find_all(self, user_id: int) -> list[Position]:
        db_user_id = await self._get_or_create_user_id(user_id)
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT symbol, quantity, avg_buy_price FROM positions WHERE user_id = $1 ORDER BY symbol",
                db_user_id,
            )
        return [
            Position(
                symbol=Symbol(str(row["symbol"])),
                quantity=Decimal(str(row["quantity"])),
                avg_buy_price=Money(Decimal(str(row["avg_buy_price"]))),
            )
            for row in rows
        ]
