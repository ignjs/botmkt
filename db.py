import os
import asyncpg
import logging
from urllib.parse import urlparse
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
logger = logging.getLogger(__name__)
_SCHEMA_READY = False

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


async def _ensure_schema_on_connection(conn):
    for statement in SCHEMA_STATEMENTS:
        await conn.execute(statement)


async def ensure_schema():
    global _SCHEMA_READY
    conn = None
    try:
        conn = await asyncpg.connect(_get_valid_database_url())
        await _ensure_schema_on_connection(conn)
        _SCHEMA_READY = True
    finally:
        if conn:
            await conn.close()


async def connect_db():
    global _SCHEMA_READY
    conn = None
    try:
        db_url = _get_valid_database_url()
        conn = await asyncpg.connect(db_url)
        if not _SCHEMA_READY:
            await _ensure_schema_on_connection(conn)
            _SCHEMA_READY = True
        return conn
    except Exception as e:
        logger.exception("Error conectando a la base de datos: %s", e)
        if conn:
            await conn.close()
        raise


async def get_user_id(conn, telegram_user_id: int) -> int:
    row = await conn.fetchrow("SELECT id FROM users WHERE telegram_user_id=$1", telegram_user_id)
    if row:
        return row["id"]
    row = await conn.fetchrow("INSERT INTO users (telegram_user_id) VALUES ($1) RETURNING id", telegram_user_id)
    return row["id"]


async def add_position(telegram_user_id: int, symbol: str, quantity: float, avg_buy_price: Optional[float] = None):
    if quantity <= 0:
        raise ValueError("quantity debe ser mayor a 0")
    if avg_buy_price is None or avg_buy_price <= 0:
        raise ValueError("avg_buy_price debe ser mayor a 0")

    conn = await connect_db()
    try:
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
    finally:
        await conn.close()


async def remove_position(telegram_user_id: int, symbol: str):
    conn = await connect_db()
    try:
        user_id = await get_user_id(conn, telegram_user_id)
        await conn.execute("DELETE FROM positions WHERE user_id=$1 AND symbol=$2", user_id, symbol)
    finally:
        await conn.close()


async def get_positions(telegram_user_id: int) -> List[Dict]:
    conn = await connect_db()
    try:
        user_id = await get_user_id(conn, telegram_user_id)
        rows = await conn.fetch(
            "SELECT symbol, quantity, avg_buy_price FROM positions WHERE user_id=$1 ORDER BY symbol",
            user_id,
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def save_investment_profile(telegram_user_id: int, profile_data: Dict) -> Dict:
    normalized = normalize_investment_profile(profile_data)
    conn = await connect_db()
    try:
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
    finally:
        await conn.close()


async def get_investment_profile(telegram_user_id: int) -> Optional[Dict]:
    conn = await connect_db()
    try:
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
    finally:
        await conn.close()
