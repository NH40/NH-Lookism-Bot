from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

import logging
from app.config.scheduler_config import (
    INCOME_TICK_MINUTES,
    UI_TICK_MINUTES,
    AUCTION_ROUND_TICK_SECONDS,
    AUCTION_START_TICK_MINUTES,
    REFERRAL_POWER_TICK_MINUTES,
    CLAN_WAR_TICK_MINUTES,
    CLAN_AUCTION_TICK_MINUTES,
)

logger = logging.getLogger(__name__)


def setup_scheduler() -> AsyncIOScheduler:
    from app.scheduler.tasks import (
        income_tick,
        ultra_instinct_tick,
        auction_round_tick,
        auction_start_tick,
        clan_war_tick,
        clan_auction_tick,
        referral_power_tick,
        daily_tick,
    )

    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        income_tick,
        trigger=IntervalTrigger(minutes=INCOME_TICK_MINUTES),
        id="income_tick",
        name="income_tick",
    )
    scheduler.add_job(
        ultra_instinct_tick,
        trigger=IntervalTrigger(minutes=UI_TICK_MINUTES),
        id="ultra_instinct_tick",
        name="ultra_instinct_tick",
    )
    # Аукцион тикает быстро — выдача наград без задержки
    scheduler.add_job(
        auction_round_tick,
        trigger=IntervalTrigger(seconds=AUCTION_ROUND_TICK_SECONDS),
        id="auction_round_tick",
        name="auction_round_tick",
        max_instances=1,
        misfire_grace_time=5,
    )
    # Новый аукцион: проверяем по расписанию
    scheduler.add_job(
        auction_start_tick,
        trigger=IntervalTrigger(minutes=AUCTION_START_TICK_MINUTES),
        id="auction_start_tick",
        name="auction_start_tick",
        max_instances=1,
        misfire_grace_time=30,
    )

    scheduler.add_job(
        referral_power_tick,
        trigger=IntervalTrigger(minutes=REFERRAL_POWER_TICK_MINUTES),
        id="referral_power_tick",
        name="referral_power_tick",
        max_instances=1,
        misfire_grace_time=60,
    )
    scheduler.add_job(
        clan_war_tick,
        trigger=IntervalTrigger(minutes=CLAN_WAR_TICK_MINUTES),
        id="clan_war_tick",
        name="clan_war_tick",
    )
    scheduler.add_job(
        clan_auction_tick,
        trigger=IntervalTrigger(minutes=CLAN_AUCTION_TICK_MINUTES),
        id="clan_auction_tick",
        name="clan_auction_tick",
        max_instances=1,
        misfire_grace_time=30,
    )

    # Ежедневные бонусы: circ_daily_districts (Архангел круг 10)
    scheduler.add_job(
        daily_tick,
        trigger=CronTrigger(hour=0, minute=0, timezone="UTC"),
        id="daily_tick",
        name="daily_tick",
        max_instances=1,
        misfire_grace_time=300,
    )

    logger.info("Scheduler configured with 8 jobs")
    return scheduler