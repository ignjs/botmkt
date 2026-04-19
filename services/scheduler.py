"""Scheduler service: runs periodic alert checks and daily AI recommendation evaluation."""
import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_MARKET_OPEN = os.getenv("MARKET_OPEN", "09:30")
_MARKET_CLOSE = os.getenv("MARKET_CLOSE", "17:00")
_MARKET_TZ = os.getenv("MARKET_TZ", "America/New_York")

_open_hour, _open_minute = (int(x) for x in _MARKET_OPEN.split(":"))
_close_hour, _close_minute = (int(x) for x in _MARKET_CLOSE.split(":"))

_scheduler: AsyncIOScheduler | None = None


def _get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone=_MARKET_TZ)
    return _scheduler


def start_scheduler(bot) -> AsyncIOScheduler:
    """Start the APScheduler with alert and recommendation jobs.

    Args:
        bot: The Telegram Bot instance used for sending messages.

    Returns:
        AsyncIOScheduler: The started scheduler instance.
    """
    from services.alert_engine import check_all_positions
    from services.recommendation_tracker import update_pending_recommendations

    scheduler = _get_scheduler()

    # E2: Alert check every 15 minutes, Mon–Fri, during market hours
    scheduler.add_job(
        check_all_positions,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=f"{_open_hour}-{_close_hour}",
            minute="*/15",
            timezone=_MARKET_TZ,
        ),
        args=[bot],
        id="alert_check",
        replace_existing=True,
    )

    # E4: Daily recommendation tracker update at 18:00 NY time
    scheduler.add_job(
        update_pending_recommendations,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=18,
            minute=0,
            timezone=_MARKET_TZ,
        ),
        id="recommendation_tracker",
        replace_existing=True,
    )

    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler iniciado (TZ=%s, mercado %s–%s)", _MARKET_TZ, _MARKET_OPEN, _MARKET_CLOSE)

    return scheduler


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler detenido.")
