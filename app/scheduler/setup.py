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
        clan_war_tick
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
    # Аукцион тикает каждые 10 секунд — быстрая выдача наград
    scheduler.add_job(
        auction_round_tick,
        trigger=IntervalTrigger(seconds=10),
        id="auction_round_tick",
        name="auction_round_tick",
        max_instances=1,
        misfire_grace_time=5,
    )
    # Новый аукцион: проверяем каждые 2 мин — пауза 10-20 мин истечёт вовремя
    scheduler.add_job(
        auction_start_tick,
        trigger=IntervalTrigger(minutes=2),
        id="auction_start_tick",
        name="auction_start_tick",
        max_instances=1,
        misfire_grace_time=30,
    )


    scheduler.add_job(clan_war_tick, "interval", minutes=5, id="clan_war_tick") 

    logger.info("Scheduler configured with 4 jobs")
    return scheduler