import asyncio
import logging
from config.container import Container
from config.settings import settings

def setup_logging() -> None:
    logging.basicConfig(level=settings.log_level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

async def main() -> None:
    setup_logging()
    container = await Container.build()
    bot = container.telegram_bot()
    try:
        await bot.run()
    finally:
        await bot.shutdown()
        await container.teardown()

if __name__ == "__main__":
    asyncio.run(main())
