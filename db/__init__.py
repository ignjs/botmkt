import json
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, List, Optional
from urllib.parse import urlparse

import asyncpg
from dotenv import load_dotenv

from services.risk_calculator import calculate_atr_stop

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
ATR_MULTIPLIER = float(os.getenv("ATR_MULTIPLIER", "2.0"))

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
        stop_loss NUMERIC,
        atr NUMERIC,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, symbol)
    )
    """,
    "ALTER TABLE positions ADD COLUMN IF NOT EXISTS stop_loss NUMERIC",
    "ALTER TABLE positions ADD COLUMN IF NOT EXISTS atr NUMERIC",
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
    """
    CREATE TABLE IF NOT EXISTS risk_snapshots (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        snapshot_date DATE NOT NULL DEFAULT CURRENT_DATE,
        var_95_pct NUMERIC,
        sharpe_ratio NUMERIC,
        max_drawdown_pct NUMERIC,
        hhi NUMERIC,
        portfolio_value NUMERIC,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, snapshot_date)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_risk_snapshots_user_id ON risk_snapshots(user_id)",
    """
    CREATE TABLE IF NOT EXISTS price_alerts (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        symbol TEXT NOT NULL,
        condition TEXT NOT NULL CHECK (condition IN ('above', 'below')),
        target_price NUMERIC NOT NULL,
        triggered BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_price_alerts_user_id ON price_alerts(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_price_alerts_triggered ON price_alerts(triggered)",
    """
    CREATE TABLE IF NOT EXISTS weekly_plans (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        week_start DATE NOT NULL,
        plan_text TEXT NOT NULL,
        actions_json JSONB,
        reviewed BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, week_start)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_weekly_plans_user_id ON weekly_plans(user_id)",
    """
    CREATE TABLE IF NOT EXISTS alerts_sent (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        symbol TEXT NOT NULL,
        alert_type TEXT NOT NULL,
        sent_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_alerts_sent_user_symbol_type_time
    ON alerts_sent(user_id, symbol, alert_type, sent_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_recommendations (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        symbol VARCHAR(20) NOT NULL,
        recommendation VARCHAR(50) NOT NULL,
        confidence INT,
        price_at_recommendation NUMERIC NOT NULL,
        recommended_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        price_5d NUMERIC,
        price_10d NUMERIC,
        price_20d NUMERIC,
        result_5d VARCHAR(10) DEFAULT 'pendiente',
        result_10d VARCHAR(10) DEFAULT 'pendiente',
        result_20d VARCHAR(10) DEFAULT 'pendiente'
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_ai_recommendations_user_date
    ON ai_recommendations(user_id, recommended_at DESC)
    """,
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
        atr_info = await calculate_atr_stop(symbol, float(avg_buy_price), ATR_MULTIPLIER)

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
                        stop_loss = $3,
                        atr = $4,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $5 AND symbol = $6
                    """,
                    new_total_qty,
                    new_avg_price,
                    atr_info["stop_loss"],
                    atr_info["atr"],
                    user_id,
                    symbol,
                )
                return f"{symbol} actualizado: {new_total_qty:.0f} @ {new_avg_price:.2f}"

            await conn.execute(
                """
                INSERT INTO positions (user_id, symbol, quantity, avg_buy_price, stop_loss, atr, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                user_id,
                symbol,
                quantity,
                avg_buy_price,
                atr_info["stop_loss"],
                atr_info["atr"],
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
                "SELECT symbol, quantity, avg_buy_price, stop_loss, atr FROM positions WHERE user_id=$1 ORDER BY symbol",
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


async def save_risk_snapshot(telegram_user_id: int, metricas: dict) -> None:
    """Persist a daily risk snapshot for a user (upsert by date).

    Args:
        telegram_user_id: Telegram user identifier.
        metricas: Dict with var_95_pct, sharpe, max_drawdown_pct, hhi, portfolio_value.

    Returns:
        None

    Raises:
        asyncpg.PostgresError: On database failure.
    """
    logger = logging.getLogger(__name__)
    try:
        async with get_conn() as conn:
            user_id = await get_user_id(conn, telegram_user_id)
            await conn.execute(
                """
                INSERT INTO risk_snapshots (user_id, snapshot_date, var_95_pct, sharpe_ratio,
                    max_drawdown_pct, hhi, portfolio_value)
                VALUES ($1, CURRENT_DATE, $2, $3, $4, $5, $6)
                ON CONFLICT (user_id, snapshot_date) DO UPDATE SET
                    var_95_pct = EXCLUDED.var_95_pct,
                    sharpe_ratio = EXCLUDED.sharpe_ratio,
                    max_drawdown_pct = EXCLUDED.max_drawdown_pct,
                    hhi = EXCLUDED.hhi,
                    portfolio_value = EXCLUDED.portfolio_value,
                    created_at = CURRENT_TIMESTAMP
                """,
                user_id,
                metricas.get("var_95_pct"),
                metricas.get("sharpe"),
                metricas.get("max_drawdown_pct"),
                metricas.get("hhi"),
                metricas.get("portfolio_value"),
            )
    except Exception as e:
        logger.exception("Error en save_risk_snapshot: %s", e)
        raise


async def get_risk_history(telegram_user_id: int, days: int = 30) -> List[Dict]:
    """Retrieve the last N days of risk snapshots for a user.

    Args:
        telegram_user_id: Telegram user identifier.
        days: Number of calendar days to look back (default 30).

    Returns:
        List[Dict]: Rows ordered by snapshot_date descending.

    Raises:
        asyncpg.PostgresError: On database failure.
    """
    logger = logging.getLogger(__name__)
    try:
        async with get_conn() as conn:
            user_id = await get_user_id(conn, telegram_user_id)
            rows = await conn.fetch(
                """
                SELECT snapshot_date, var_95_pct, sharpe_ratio, max_drawdown_pct, hhi, portfolio_value
                FROM risk_snapshots
                WHERE user_id = $1 AND snapshot_date >= CURRENT_DATE - $2::INTEGER
                ORDER BY snapshot_date DESC
                """,
                user_id,
                days,
            )
            return [dict(row) for row in rows]
    except Exception as e:
        logger.exception("Error en get_risk_history: %s", e)
        raise


async def add_price_alert(
    telegram_user_id: int, symbol: str, condition: str, target_price: float
) -> int:
    """Create a new price alert for a user.

    Args:
        telegram_user_id: Telegram user identifier.
        symbol: Ticker symbol.
        condition: 'above' or 'below'.
        target_price: Target price threshold.

    Returns:
        int: ID of the newly created alert.

    Raises:
        ValueError: If condition is not 'above' or 'below'.
        asyncpg.PostgresError: On database failure.
    """
    logger = logging.getLogger(__name__)
    if condition not in ("above", "below"):
        raise ValueError("condition debe ser 'above' o 'below'")
    try:
        async with get_conn() as conn:
            user_id = await get_user_id(conn, telegram_user_id)
            row = await conn.fetchrow(
                """
                INSERT INTO price_alerts (user_id, symbol, condition, target_price)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                user_id, symbol, condition, target_price,
            )
            return row["id"]
    except Exception as e:
        logger.exception("Error en add_price_alert: %s", e)
        raise


async def get_user_alerts(telegram_user_id: int) -> List[Dict]:
    """Get all active (non-triggered) alerts for a user.

    Args:
        telegram_user_id: Telegram user identifier.

    Returns:
        List[Dict]: Alert records ordered by creation date.

    Raises:
        asyncpg.PostgresError: On database failure.
    """
    logger = logging.getLogger(__name__)
    try:
        async with get_conn() as conn:
            user_id = await get_user_id(conn, telegram_user_id)
            rows = await conn.fetch(
                """
                SELECT id, symbol, condition, target_price, triggered, created_at
                FROM price_alerts
                WHERE user_id = $1 AND triggered = FALSE
                ORDER BY created_at DESC
                """,
                user_id,
            )
            return [dict(row) for row in rows]
    except Exception as e:
        logger.exception("Error en get_user_alerts: %s", e)
        raise


async def delete_price_alert(telegram_user_id: int, alert_id: int) -> bool:
    """Delete a price alert by ID for a given user.

    Args:
        telegram_user_id: Telegram user identifier.
        alert_id: Alert ID to delete.

    Returns:
        bool: True if the alert was found and deleted, False otherwise.

    Raises:
        asyncpg.PostgresError: On database failure.
    """
    logger = logging.getLogger(__name__)
    try:
        async with get_conn() as conn:
            user_id = await get_user_id(conn, telegram_user_id)
            result = await conn.execute(
                "DELETE FROM price_alerts WHERE id = $1 AND user_id = $2",
                alert_id, user_id,
            )
            return result == "DELETE 1"
    except Exception as e:
        logger.exception("Error en delete_price_alert: %s", e)
        raise


async def get_all_active_alerts() -> List[Dict]:
    """Get all non-triggered alerts across all users.

    Returns:
        List[Dict]: All active alert records with telegram_user_id included.

    Raises:
        asyncpg.PostgresError: On database failure.
    """
    logger = logging.getLogger(__name__)
    try:
        async with get_conn() as conn:
            rows = await conn.fetch(
                """
                SELECT pa.id, u.telegram_user_id, pa.symbol, pa.condition, pa.target_price
                FROM price_alerts pa
                JOIN users u ON pa.user_id = u.id
                WHERE pa.triggered = FALSE
                ORDER BY pa.symbol
                """
            )
            return [dict(row) for row in rows]
    except Exception as e:
        logger.exception("Error en get_all_active_alerts: %s", e)
        raise


async def mark_alert_triggered(alert_id: int) -> None:
    """Mark a price alert as triggered.

    Args:
        alert_id: Alert ID to mark as triggered.

    Returns:
        None

    Raises:
        asyncpg.PostgresError: On database failure.
    """
    logger = logging.getLogger(__name__)
    try:
        async with get_conn() as conn:
            await conn.execute(
                "UPDATE price_alerts SET triggered = TRUE WHERE id = $1",
                alert_id,
            )
    except Exception as e:
        logger.exception("Error en mark_alert_triggered: %s", e)
        raise


async def get_positions_for_alerting() -> List[Dict]:
    """Return all active positions with user identifiers for proactive alerting."""
    logger = logging.getLogger(__name__)
    try:
        async with get_conn() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    u.id AS user_id,
                    u.telegram_user_id,
                    p.symbol,
                    p.quantity,
                    p.avg_buy_price,
                    p.stop_loss,
                    p.atr
                FROM positions p
                JOIN users u ON p.user_id = u.id
                WHERE p.quantity > 0
                ORDER BY u.id, p.symbol
                """
            )
            return [dict(row) for row in rows]
    except Exception as e:
        logger.exception("Error en get_positions_for_alerting: %s", e)
        raise


async def was_alert_sent_recently(
    user_id: int,
    symbol: str,
    alert_type: str,
    cooldown_hours: int,
) -> bool:
    """Check if same alert was already sent inside cooldown window."""
    logger = logging.getLogger(__name__)
    try:
        async with get_conn() as conn:
            row = await conn.fetchrow(
                """
                SELECT 1
                FROM alerts_sent
                WHERE user_id = $1
                  AND symbol = $2
                  AND alert_type = $3
                                    AND sent_at >= NOW() - ($4 * INTERVAL '1 hour')
                LIMIT 1
                """,
                user_id,
                symbol,
                alert_type,
                cooldown_hours,
            )
            return row is not None
    except Exception as e:
        logger.exception("Error en was_alert_sent_recently: %s", e)
        raise


async def record_sent_alert(user_id: int, symbol: str, alert_type: str) -> None:
    """Persist a sent proactive alert event."""
    logger = logging.getLogger(__name__)
    try:
        async with get_conn() as conn:
            await conn.execute(
                """
                INSERT INTO alerts_sent (user_id, symbol, alert_type, sent_at)
                VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
                """,
                user_id,
                symbol,
                alert_type,
            )
    except Exception as e:
        logger.exception("Error en record_sent_alert: %s", e)
        raise


async def get_recent_sent_alerts(telegram_user_id: int, hours: int = 24) -> List[Dict]:
    """Return sent proactive alerts for a user in the last N hours."""
    logger = logging.getLogger(__name__)
    try:
        async with get_conn() as conn:
            user_id = await get_user_id(conn, telegram_user_id)
            rows = await conn.fetch(
                """
                SELECT symbol, alert_type, sent_at
                FROM alerts_sent
                WHERE user_id = $1
                                    AND sent_at >= NOW() - ($2 * INTERVAL '1 hour')
                ORDER BY sent_at DESC
                """,
                user_id,
                hours,
            )
            return [dict(row) for row in rows]
    except Exception as e:
        logger.exception("Error en get_recent_sent_alerts: %s", e)
        raise


async def save_ai_recommendation(
    telegram_user_id: int,
    symbol: str,
    recommendation: str,
    confidence: Optional[int],
    price_at_recommendation: float,
) -> None:
    """Persist AI recommendation metadata for later hit-rate evaluation."""
    logger = logging.getLogger(__name__)
    try:
        async with get_conn() as conn:
            user_id = await get_user_id(conn, telegram_user_id)
            await conn.execute(
                """
                INSERT INTO ai_recommendations (
                    user_id,
                    symbol,
                    recommendation,
                    confidence,
                    price_at_recommendation,
                    recommended_at,
                    result_5d,
                    result_10d,
                    result_20d
                )
                VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP, 'pendiente', 'pendiente', 'pendiente')
                """,
                user_id,
                symbol,
                recommendation,
                confidence,
                price_at_recommendation,
            )
    except Exception as e:
        logger.exception("Error en save_ai_recommendation: %s", e)
        raise


async def get_pending_ai_recommendations() -> List[Dict]:
    """Return recommendations with at least one pending horizon result."""
    logger = logging.getLogger(__name__)
    try:
        async with get_conn() as conn:
            rows = await conn.fetch(
                """
                SELECT id, user_id, symbol, recommendation, price_at_recommendation,
                       recommended_at, price_5d, price_10d, price_20d,
                       result_5d, result_10d, result_20d
                FROM ai_recommendations
                WHERE result_5d = 'pendiente'
                   OR result_10d = 'pendiente'
                   OR result_20d = 'pendiente'
                ORDER BY recommended_at ASC
                """
            )
            return [dict(row) for row in rows]
    except Exception as e:
        logger.exception("Error en get_pending_ai_recommendations: %s", e)
        raise


async def update_ai_recommendation_horizon(
    recommendation_id: int,
    horizon_days: int,
    price_value: float,
    result_value: str,
) -> None:
    """Update one horizon field pair (price_Nd, result_Nd) for a recommendation."""
    logger = logging.getLogger(__name__)
    if horizon_days not in (5, 10, 20):
        raise ValueError("horizon_days inválido")

    price_column = f"price_{horizon_days}d"
    result_column = f"result_{horizon_days}d"
    try:
        async with get_conn() as conn:
            await conn.execute(
                f"""
                UPDATE ai_recommendations
                SET {price_column} = $1,
                    {result_column} = $2
                WHERE id = $3
                """,
                price_value,
                result_value,
                recommendation_id,
            )
    except Exception as e:
        logger.exception("Error en update_ai_recommendation_horizon: %s", e)
        raise


async def get_recent_ai_recommendations(telegram_user_id: int, limit: int = 10) -> List[Dict]:
    """Get latest AI recommendations for a user."""
    logger = logging.getLogger(__name__)
    try:
        async with get_conn() as conn:
            user_id = await get_user_id(conn, telegram_user_id)
            rows = await conn.fetch(
                """
                SELECT symbol, recommendation, price_at_recommendation, recommended_at,
                       price_5d, price_10d, price_20d,
                       result_5d, result_10d, result_20d
                FROM ai_recommendations
                WHERE user_id = $1
                ORDER BY recommended_at DESC
                LIMIT $2
                """,
                user_id,
                limit,
            )
            return [dict(row) for row in rows]
    except Exception as e:
        logger.exception("Error en get_recent_ai_recommendations: %s", e)
        raise


async def get_ai_hit_rate_summary(telegram_user_id: int) -> Dict:
    """Compute user AI hit-rate excluding pending evaluations."""
    logger = logging.getLogger(__name__)
    try:
        async with get_conn() as conn:
            user_id = await get_user_id(conn, telegram_user_id)
            rows = await conn.fetch(
                """
                SELECT result_5d, result_10d, result_20d
                FROM ai_recommendations
                WHERE user_id = $1
                """,
                user_id,
            )

            total = 0
            ok = 0
            for row in rows:
                for key in ("result_5d", "result_10d", "result_20d"):
                    value = row[key]
                    if value == "pendiente":
                        continue
                    total += 1
                    if value == "acierto":
                        ok += 1

            hit_rate = (ok / total * 100.0) if total > 0 else 0.0
            return {"correct": ok, "total": total, "hit_rate_pct": round(hit_rate, 1)}
    except Exception as e:
        logger.exception("Error en get_ai_hit_rate_summary: %s", e)
        raise


async def save_weekly_plan(
    telegram_user_id: int, plan_text: str, actions: Optional[List] = None
) -> None:
    """Persist the weekly plan for a user (upsert by week_start = current Monday).

    Args:
        telegram_user_id: Telegram user identifier.
        plan_text: Full plan text in Markdown.
        actions: Optional list of action dicts.

    Returns:
        None

    Raises:
        asyncpg.PostgresError: On database failure.
    """
    logger = logging.getLogger(__name__)
    try:
        actions_json = json.dumps(actions or [], ensure_ascii=False)
        async with get_conn() as conn:
            user_id = await get_user_id(conn, telegram_user_id)
            await conn.execute(
                """
                INSERT INTO weekly_plans (user_id, week_start, plan_text, actions_json)
                VALUES ($1, DATE_TRUNC('week', CURRENT_DATE), $2, $3)
                ON CONFLICT (user_id, week_start) DO UPDATE SET
                    plan_text = EXCLUDED.plan_text,
                    actions_json = EXCLUDED.actions_json,
                    created_at = CURRENT_TIMESTAMP
                """,
                user_id,
                plan_text,
                actions_json,
            )
    except Exception as e:
        logger.exception("Error en save_weekly_plan: %s", e)
        raise


async def get_last_weekly_plan(telegram_user_id: int) -> Optional[Dict]:
    """Retrieve the most recent weekly plan for a user (excluding the current week).

    Args:
        telegram_user_id: Telegram user identifier.

    Returns:
        Optional[Dict]: The previous week's plan record, or None if not found.

    Raises:
        asyncpg.PostgresError: On database failure.
    """
    logger = logging.getLogger(__name__)
    try:
        async with get_conn() as conn:
            user_id = await get_user_id(conn, telegram_user_id)
            row = await conn.fetchrow(
                """
                SELECT week_start, plan_text, actions_json, reviewed
                FROM weekly_plans
                WHERE user_id = $1 AND week_start < DATE_TRUNC('week', CURRENT_DATE)
                ORDER BY week_start DESC
                LIMIT 1
                """,
                user_id,
            )
            return dict(row) if row else None
    except Exception as e:
        logger.exception("Error en get_last_weekly_plan: %s", e)
        raise


async def sync_broker_order(
    telegram_user_id: int,
    symbol: str,
    qty: float,
    side: str,
    price: float,
) -> None:
    """Sync executed broker order into local positions table."""
    logger = logging.getLogger(__name__)
    try:
        async with get_conn() as conn:
            user_id = await get_user_id(conn, telegram_user_id)
            existing = await conn.fetchrow(
                """
                SELECT quantity, avg_buy_price
                FROM positions
                WHERE user_id = $1 AND symbol = $2
                """,
                user_id,
                symbol,
            )

            if side == "buy":
                if existing:
                    old_qty = float(existing["quantity"])
                    old_avg = float(existing["avg_buy_price"])
                    new_qty = old_qty + qty
                    new_avg = ((old_qty * old_avg) + (qty * price)) / new_qty
                    await conn.execute(
                        """
                        UPDATE positions
                        SET quantity = $1,
                            avg_buy_price = $2,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = $3 AND symbol = $4
                        """,
                        new_qty,
                        new_avg,
                        user_id,
                        symbol,
                    )
                else:
                    await conn.execute(
                        """
                        INSERT INTO positions (user_id, symbol, quantity, avg_buy_price, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        """,
                        user_id,
                        symbol,
                        qty,
                        price,
                    )
                return

            if side == "sell":
                if not existing:
                    return
                old_qty = float(existing["quantity"])
                remaining = old_qty - qty
                if remaining <= 0:
                    await conn.execute(
                        "DELETE FROM positions WHERE user_id = $1 AND symbol = $2",
                        user_id,
                        symbol,
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE positions
                        SET quantity = $1,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = $2 AND symbol = $3
                        """,
                        remaining,
                        user_id,
                        symbol,
                    )
    except Exception as e:
        logger.exception("Error en sync_broker_order: %s", e)
        raise

