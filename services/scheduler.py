import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import settings
from services.alert_engine import check_all_positions
from services.recommendation_tracker import update_pending_recommendations

logger = logging.getLogger(__name__)


def _in_market_window(now: datetime, open_hour: int, open_minute: int, close_hour: int, close_minute: int) -> bool:
    if now.weekday() > 4:
        return False
    start = now.replace(hour=open_hour, minute=open_minute, second=0, microsecond=0)
    end = now.replace(hour=close_hour, minute=close_minute, second=59, microsecond=999999)
    return start <= now <= end


async def _run_alert_scan(bot, tz: ZoneInfo, open_hour: int, open_minute: int, close_hour: int, close_minute: int):
    now = datetime.now(tz)
    if not _in_market_window(now, open_hour, open_minute, close_hour, close_minute):
        return
    await check_all_positions(bot=bot)


class BotScheduler:
    """Application-level scheduler for proactive periodic jobs."""

    def __init__(self) -> None:
        self._scheduler: AsyncIOScheduler | None = None

    def start(self, bot) -> None:
        if self._scheduler and self._scheduler.running:
            return

        tz = ZoneInfo(settings.market_tz)
        self._scheduler = AsyncIOScheduler(timezone=tz)

        open_hour, open_minute = [int(v) for v in settings.market_open.split(":", maxsplit=1)]
        close_hour, close_minute = [int(v) for v in settings.market_close.split(":", maxsplit=1)]

        self._scheduler.add_job(
            _run_alert_scan,
            trigger=CronTrigger(
                day_of_week="mon-fri",
                hour="*",
                minute="*/15",
                timezone=tz,
            ),
            kwargs={
                "bot": bot,
                "tz": tz,
                "open_hour": open_hour,
                "open_minute": open_minute,
                "close_hour": close_hour,
                "close_minute": close_minute,
            },
            id="proactive_alerts_15m",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=120,
        )

        self._scheduler.add_job(
            update_pending_recommendations,
            trigger=CronTrigger(hour=20, minute=5, timezone=tz),
            id="ai_recommendation_tracker_daily",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )

        self._scheduler.start()
        logger.info(
            "Scheduler iniciado (%s-%s %s cada 15m)",
            settings.market_open,
            settings.market_close,
            settings.market_tz,
        )

        now = datetime.now(tz)
        in_hours = (
            now.weekday() <= 4
            and (now.hour > open_hour or (now.hour == open_hour and now.minute >= open_minute))
            and (now.hour < close_hour or (now.hour == close_hour and now.minute <= close_minute))
        )
        if in_hours:
            self._scheduler.add_job(
                _run_alert_scan,
                kwargs={
                    "bot": bot,
                    "tz": tz,
                    "open_hour": open_hour,
                    "open_minute": open_minute,
                    "close_hour": close_hour,
                    "close_minute": close_minute,
                },
                id="proactive_alerts_bootstrap",
                replace_existing=True,
            )

    def shutdown(self) -> None:
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Scheduler detenido")


scheduler_manager = BotScheduler()
