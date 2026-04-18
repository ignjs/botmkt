import os
import asyncpg
import logging
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from typing import AsyncIterator, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
logger = logging.getLogger(__name__)
_SCHEMA_READY = False
_pool: Optional[asyncpg.Pool] = None

ALLOWED_HORIZONS = {"corto", "mediano", "largo"}
ALLOWED_STRATEGIES = {"growth", "dividendos", "valor", "mixta"}
DEFAULT_PROFILE = {
    "risk_tolerance": 5,
    "investment_horizon": "largo",
    "max_position_pct": 25,
    "max_country_pct": 70,
    "max_sector_pct": 50,
    "max_drawdown_pct": 12,
    "preferred_strategy": "mixta",
    "cash_buffer_pct": 10,
}

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        telegram_user_id BIGINT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS positions (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        symbol TEXT NOT NULL,
        quantity NUMERIC NOT NULL,
        avg_buy_price NUMERIC NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, symbol)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS investment_profiles (
        user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        risk_tolerance INTEGER NOT NULL CHECK (risk_tolerance BETWEEN 1 AND 10),
        investment_horizon TEXT NOT NULL CHECK (investment_horizon IN ('corto', 'mediano', 'largo')),
        max_position_pct NUMERIC NOT NULL CHECK (max_position_pct > 0 AND max_position_pct <= 100),
        max_country_pct NUMERIC NOT NULL CHECK (max_country_pct > 0 AND max_country_pct <= 100),
        max_sector_pct NUMERIC NOT NULL CHECK (max_sector_pct > 0 AND max_sector_pct <= 100),
        max_drawdown_pct NUMERIC NOT NULL CHECK (max_drawdown_pct >= 0 AND max_drawdown_pct <= 100),
        preferred_strategy TEXT NOT NULL CHECK (preferred_strategy IN ('growth', 'dividendos', 'valor', 'mixta')),
        cash_buffer_pct NUMERIC NOT NULL CHECK (cash_buffer_pct >= 0 AND cash_buffer_pct <= 100),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_positions_user_id ON positions(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_investment_profiles_updated_at ON investment_profiles(updated_at)",
]


def _get_valid_database_url() -> str:
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL no está configurada. Define la variable en tu entorno o en .env")

    db_url = DATABASE_URL.strip().strip('"').strip("'")
    parsed = urlparse(db_url)
    if parsed.scheme not in {"postgresql", "postgres"} or not parsed.hostname or not parsed.path:
        raise ValueError(
            "DATABASE_URL inválida. Usa formato: postgresql://usuario:password@host:5432/nombre_db"
        )
    return db_url


def _normalize_percentage(value: float, field_name: str) -> float:
    normalized = float(value)
    if not 0 <= normalized <= 100:
        raise ValueError(f"{field_name} debe estar entre 0 y 100")
    return round(normalized, 2)


def normalize_investment_profile(profile_data: Dict) -> Dict:
    data = {**DEFAULT_PROFILE, **(profile_data or {})}
    data["risk_tolerance"] = int(data["risk_tolerance"])
    if not 1 <= data["risk_tolerance"] <= 10:
        raise ValueError("risk_tolerance debe estar entre 1 y 10")

    data["investment_horizon"] = str(data["investment_horizon"]).strip().lower()
    if data["investment_horizon"] not in ALLOWED_HORIZONS:
        raise ValueError("investment_horizon inválido")

    data["preferred_strategy"] = str(data["preferred_strategy"]).strip().lower()
    if data["preferred_strategy"] not in ALLOWED_STRATEGIES:
        raise ValueError("preferred_strategy inválido")

    for key in (
        "max_position_pct",
        "max_country_pct",
        "max_sector_pct",
        "max_drawdown_pct",
        "cash_buffer_pct",
    ):
        data[key] = _normalize_percentage(data[key], key)

    return data


async def init_pool() -> None:
    """Initialise the global asyncpg connection pool.

    Args:
        None

    Returns:
        None — sets the module-level ``_pool`` variable.

    Raises:
        ValueError: If DATABASE_URL is invalid.
        asyncpg.PostgresError: On connection failure.
    """
    global _pool, _SCHEMA_READY
    logger = logging.getLogger(__name__)
    try:
        db_url = _get_valid_database_url()
        _pool = await asyncpg.create_pool(
            db_url,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        async with _pool.acquire() as conn:
            await _ensure_schema_on_connection(conn)
        _SCHEMA_READY = True
        logger.info("Connection pool initialised (min=2, max=10)")
    except Exception as e:
        logger.exception("Error initialising connection pool: %s", e)
        raise


@asynccontextmanager
async def get_conn() -> AsyncIterator[asyncpg.Connection]:
    """Async context manager that yields a connection from the pool.

    Initialises the pool lazily if it has not been created yet.

    Args:
        None

    Returns:
        asyncpg.Connection: A pooled database connection.

    Raises:
        asyncpg.PostgresError: On connection failure.
    """
    global _pool
    logger = logging.getLogger(__name__)
    if _pool is None:
        await init_pool()
    try:
        async with _pool.acquire() as conn:
            yield conn
    except Exception as e:
        logger.exception("Error acquiring connection from pool: %s", e)
        raise


async def _ensure_schema_on_connection(conn) -> None:
    for statement in SCHEMA_STATEMENTS:
        await conn.execute(statement)


async def ensure_schema() -> None:
    """Ensure all required DB tables exist.

    Creates the pool (if needed) and runs all schema statements.

    Args:
        None

    Returns:
        None

    Raises:
        asyncpg.PostgresError: On schema creation failure.
    """
    global _SCHEMA_READY
    logger = logging.getLogger(__name__)
    try:
        async with get_conn() as conn:
            await _ensure_schema_on_connection(conn)
        _SCHEMA_READY = True
    except Exception as e:
        logger.exception("Error ensuring schema: %s", e)
        raise


async def get_user_id(conn, telegram_user_id: int) -> int:
    row = await conn.fetchrow("SELECT id FROM users WHERE telegram_user_id=$1", telegram_user_id)
    if row:
        return row["id"]
    row = await conn.fetchrow("INSERT INTO users (telegram_user_id) VALUES ($1) RETURNING id", telegram_user_id)
    return row["id"]


async def add_position(telegram_user_id: int, symbol: str, quantity: float, avg_buy_price: Optional[float] = None):
    """Add or update a portfolio position for a user.

    Args:
        telegram_user_id: Telegram user identifier.
        symbol: Ticker symbol (e.g. AAPL).
        quantity: Number of shares/units (must be > 0).
        avg_buy_price: Average purchase price per unit (must be > 0).

    Returns:
        str: Confirmation message with updated position details.

    Raises:
        ValueError: If quantity or avg_buy_price are invalid.
        asyncpg.PostgresError: On database failure.
    """
    logger = logging.getLogger(__name__)
    if quantity <= 0:
        raise ValueError("quantity debe ser mayor a 0")
    if avg_buy_price is None or avg_buy_price <= 0:
        raise ValueError("avg_buy_price debe ser mayor a 0")

    try:
        async with get_conn() as conn:
            user_id = await get_user_id(conn, telegram_user_id)
            existing = await conn.fetchrow(
                """
                SELECT quantity, avg_buy_price FROM positions
                WHERE user_id = $1 AND symbol = $2
                """,
                user_id,
                symbol,
            )

            if existing:
                old_qty = float(existing["quantity"])
                old_avg = float(existing["avg_buy_price"] or 0)
                new_total_qty = old_qty + quantity
                new_avg_price = (old_avg * old_qty + avg_buy_price * quantity) / new_total_qty

                await conn.execute(
                    """
                    UPDATE positions SET
                        quantity = $1,
                        avg_buy_price = $2,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $3 AND symbol = $4
                    """,
                    new_total_qty,
                    new_avg_price,
                    user_id,
                    symbol,
                )
                return f"{symbol} actualizado: {new_total_qty:.0f} @ {new_avg_price:.2f}"

            await conn.execute(
                """
                INSERT INTO positions (user_id, symbol, quantity, avg_buy_price, created_at, updated_at)
                VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                user_id,
                symbol,
                quantity,
                avg_buy_price,
            )
            return f"{symbol} agregado: {quantity:.0f} @ {avg_buy_price:.2f}"
    except Exception as e:
        logger.exception("Error en add_position: %s", e)
        raise


async def remove_position(telegram_user_id: int, symbol: str) -> None:
    """Remove a portfolio position for a user.

    Args:
        telegram_user_id: Telegram user identifier.
        symbol: Ticker symbol to remove.

    Returns:
        None

    Raises:
        asyncpg.PostgresError: On database failure.
    """
    logger = logging.getLogger(__name__)
    try:
        async with get_conn() as conn:
            user_id = await get_user_id(conn, telegram_user_id)
            await conn.execute("DELETE FROM positions WHERE user_id=$1 AND symbol=$2", user_id, symbol)
    except Exception as e:
        logger.exception("Error en remove_position: %s", e)
        raise


async def get_positions(telegram_user_id: int) -> List[Dict]:
    """Retrieve all portfolio positions for a user.

    Args:
        telegram_user_id: Telegram user identifier.

    Returns:
        List[Dict]: List of position records with symbol, quantity, avg_buy_price.

    Raises:
        asyncpg.PostgresError: On database failure.
    """
    logger = logging.getLogger(__name__)
    try:
        async with get_conn() as conn:
            user_id = await get_user_id(conn, telegram_user_id)
            rows = await conn.fetch(
                "SELECT symbol, quantity, avg_buy_price FROM positions WHERE user_id=$1 ORDER BY symbol",
                user_id,
            )
            return [dict(row) for row in rows]
    except Exception as e:
        logger.exception("Error en get_positions: %s", e)
        raise


async def save_investment_profile(telegram_user_id: int, profile_data: Dict) -> Dict:
    """Persist an investment profile for a user (upsert).

    Args:
        telegram_user_id: Telegram user identifier.
        profile_data: Raw profile dict; unknown keys are ignored and defaults applied.

    Returns:
        Dict: The saved profile record as returned by the database.

    Raises:
        ValueError: If profile_data contains invalid values.
        asyncpg.PostgresError: On database failure.
    """
    logger = logging.getLogger(__name__)
    normalized = normalize_investment_profile(profile_data)
    try:
        async with get_conn() as conn:
            user_id = await get_user_id(conn, telegram_user_id)
            row = await conn.fetchrow(
                """
                INSERT INTO investment_profiles (
                    user_id,
                    risk_tolerance,
                    investment_horizon,
                    max_position_pct,
                    max_country_pct,
                    max_sector_pct,
                    max_drawdown_pct,
                    preferred_strategy,
                    cash_buffer_pct,
                    created_at,
                    updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
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
                RETURNING risk_tolerance, investment_horizon, max_position_pct, max_country_pct,
                          max_sector_pct, max_drawdown_pct, preferred_strategy, cash_buffer_pct,
                          created_at, updated_at
                """,
                user_id,
                normalized["risk_tolerance"],
                normalized["investment_horizon"],
                normalized["max_position_pct"],
                normalized["max_country_pct"],
                normalized["max_sector_pct"],
                normalized["max_drawdown_pct"],
                normalized["preferred_strategy"],
                normalized["cash_buffer_pct"],
            )
            return dict(row)
    except Exception as e:
        logger.exception("Error en save_investment_profile: %s", e)
        raise


async def get_investment_profile(telegram_user_id: int) -> Optional[Dict]:
    """Retrieve an investment profile for a user.

    Args:
        telegram_user_id: Telegram user identifier.

    Returns:
        Optional[Dict]: Profile record, or None if not set.

    Raises:
        asyncpg.PostgresError: On database failure.
    """
    logger = logging.getLogger(__name__)
    try:
        async with get_conn() as conn:
            user_id = await get_user_id(conn, telegram_user_id)
            row = await conn.fetchrow(
                """
                SELECT risk_tolerance, investment_horizon, max_position_pct, max_country_pct,
                       max_sector_pct, max_drawdown_pct, preferred_strategy, cash_buffer_pct,
                       created_at, updated_at
                FROM investment_profiles
                WHERE user_id = $1
                """,
                user_id,
            )
            return dict(row) if row else None
    except Exception as e:
        logger.exception("Error en get_investment_profile: %s", e)
        raise
