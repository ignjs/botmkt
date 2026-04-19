from application.ports.profile_repository_port import ProfileRepositoryPort
from domain.entities.investment_profile import InvestmentProfile
from infrastructure.database.pool import get_pool


class PostgresProfileRepository(ProfileRepositoryPort):
    """Repositorio PostgreSQL de perfiles de inversión."""

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

    async def save(self, user_id: int, profile: InvestmentProfile) -> None:
        db_user_id = await self._get_or_create_user_id(user_id)
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO investment_profiles (
                    user_id, risk_tolerance, investment_horizon,
                    max_position_pct, max_country_pct, max_sector_pct,
                    max_drawdown_pct, preferred_strategy, cash_buffer_pct
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                ON CONFLICT (user_id) DO UPDATE SET
                    risk_tolerance = EXCLUDED.risk_tolerance,
                    investment_horizon = EXCLUDED.investment_horizon,
                    max_position_pct = EXCLUDED.max_position_pct,
                    max_country_pct = EXCLUDED.max_country_pct,
                    max_sector_pct = EXCLUDED.max_sector_pct,
                    max_drawdown_pct = EXCLUDED.max_drawdown_pct,
                    preferred_strategy = EXCLUDED.preferred_strategy,
                    cash_buffer_pct = EXCLUDED.cash_buffer_pct,
                    updated_at = CURRENT_TIMESTAMP
                """,
                db_user_id,
                profile.risk_tolerance,
                profile.investment_horizon,
                profile.max_position_pct,
                profile.max_country_pct,
                profile.max_sector_pct,
                profile.max_drawdown_pct,
                profile.preferred_strategy,
                profile.cash_buffer_pct,
            )

    async def find(self, user_id: int) -> InvestmentProfile | None:
        db_user_id = await self._get_or_create_user_id(user_id)
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT risk_tolerance, investment_horizon,
                       max_position_pct, max_country_pct, max_sector_pct,
                       max_drawdown_pct, preferred_strategy, cash_buffer_pct
                FROM investment_profiles WHERE user_id = $1
                """,
                db_user_id,
            )
        if row is None:
            return None
        return InvestmentProfile(
            risk_tolerance=int(row["risk_tolerance"]),
            investment_horizon=str(row["investment_horizon"]),
            max_position_pct=float(row["max_position_pct"]),
            max_country_pct=float(row["max_country_pct"]),
            max_sector_pct=float(row["max_sector_pct"]),
            max_drawdown_pct=float(row["max_drawdown_pct"]),
            preferred_strategy=str(row["preferred_strategy"]),
            cash_buffer_pct=float(row["cash_buffer_pct"]),
        )
