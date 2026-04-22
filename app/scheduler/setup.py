from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.scheduler.tasks import income_tick, ultra_instinct_tick, auction_tick
import logging

logger = logging.getLogger(__name__)


def setup_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Доход — каждую минуту
    scheduler.add_job(
        income_tick,
        trigger=IntervalTrigger(minutes=1),
        id="income_tick",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=30,
    )

    # УИ авто-действия — каждую минуту
    scheduler.add_job(
        ultra_instinct_tick,
        trigger=IntervalTrigger(minutes=1),
        id="ui_tick",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=30,
    )

    # Аукцион — каждую минуту
    scheduler.add_job(
        auction_tick,
        trigger=IntervalTrigger(minutes=1),
        id="auction_tick",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=30,
    )

    logger.info("Scheduler configured with 3 jobs")
    return scheduler