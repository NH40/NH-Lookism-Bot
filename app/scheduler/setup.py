from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging

logger = logging.getLogger(__name__)


def setup_scheduler() -> AsyncIOScheduler:
    from app.scheduler.tasks import (
        income_tick,
        ultra_instinct_tick,
        auction_round_tick,
        auction_start_tick,
    )

    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        income_tick,
        trigger=IntervalTrigger(minutes=1),
        id="income_tick",
        name="income_tick",
    )
    scheduler.add_job(
        ultra_instinct_tick,
        trigger=IntervalTrigger(minutes=1),
        id="ultra_instinct_tick",
        name="ultra_instinct_tick",
    )
    # Аукцион тикает каждые 30 секунд
    scheduler.add_job(
        auction_round_tick,
        trigger=IntervalTrigger(seconds=30),
        id="auction_round_tick",
        name="auction_round_tick",
    )
    # Новый аукцион раз в 15 минут (случайно 10-20)
    scheduler.add_job(
        auction_start_tick,
        trigger=IntervalTrigger(minutes=15),
        id="auction_start_tick",
        name="auction_start_tick",
    )

    logger.info("Scheduler configured with 4 jobs")
    return scheduler