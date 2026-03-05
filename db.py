import os
import asyncpg
import logging
from urllib.parse import urlparse
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
logger = logging.getLogger(__name__)


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


async def connect_db():
    try:
        db_url = _get_valid_database_url()
        return await asyncpg.connect(db_url)
    except Exception as e:
        logger.exception("Error conectando a la base de datos: %s", e)
        raise

async def get_user_id(conn, telegram_user_id: int) -> int:
    row = await conn.fetchrow("SELECT id FROM users WHERE telegram_user_id=$1", telegram_user_id)
    if row:
        return row["id"]
    row = await conn.fetchrow("INSERT INTO users (telegram_user_id) VALUES ($1) RETURNING id", telegram_user_id)
    return row["id"]

async def add_position(telegram_user_id: int, symbol: str, quantity: float, avg_buy_price: float = None):
    conn = await connect_db()
    user_id = await get_user_id(conn, telegram_user_id)
    
    # 1. Buscar posición existente
    existing = await conn.fetchrow("""
        SELECT quantity, avg_buy_price FROM positions 
        WHERE user_id = $1 AND symbol = $2
    """, user_id, symbol)
    
    if existing:
        # 2. UPSERT PONDERADO
        old_qty = float(existing['quantity'])
        old_avg = float(existing['avg_buy_price'] or 0)
        new_total_qty = old_qty + quantity
        new_avg_price = (old_avg * old_qty + avg_buy_price * quantity) / new_total_qty
        
        await conn.execute("""
            UPDATE positions SET 
                quantity = $1, 
                avg_buy_price = $2, 
                updated_at = NOW()
            WHERE user_id = $3 AND symbol = $4
        """, new_total_qty, new_avg_price, user_id, symbol)
        
        result = f"{symbol} actualizado: {new_total_qty:.0f} @ {new_avg_price:.2f}"
    else:
        # 3. INSERT nuevo
        await conn.execute("""
            INSERT INTO positions (user_id, symbol, quantity, avg_buy_price, created_at, updated_at)
            VALUES ($1, $2, $3, $4, NOW(), NOW())
        """, user_id, symbol, quantity, avg_buy_price)
        
        result = f"{symbol} agregado: {quantity:.0f} @ {avg_buy_price:.2f}"
    
    await conn.close()
    return result

async def remove_position(telegram_user_id: int, symbol: str):
    conn = await connect_db()
    user_id = await get_user_id(conn, telegram_user_id)
    await conn.execute('''DELETE FROM positions WHERE user_id=$1 AND symbol=$2''', user_id, symbol)
    await conn.close()

async def get_positions(telegram_user_id: int) -> List[Dict]:
    conn = await connect_db()
    user_id = await get_user_id(conn, telegram_user_id)
    rows = await conn.fetch('''SELECT symbol, quantity, avg_buy_price FROM positions WHERE user_id=$1''', user_id)
    await conn.close()
    return [dict(row) for row in rows]
