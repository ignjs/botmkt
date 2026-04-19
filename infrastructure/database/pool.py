import asyncpg

from config.settings import settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Retorna un singleton de connection pool asyncpg."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)
    return _pool


async def close_pool() -> None:
    """Cierra y limpia el pool global."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
