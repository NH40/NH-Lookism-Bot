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
    CAMPAIGN_TICK_MINUTES,
    BOSS_TICK_SECONDS,
    REGION_WAR_TICK_MINUTES,
    ACHIEVEMENT_TICK_MINUTES,
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
        region_war_tick,
        referral_power_tick,
        daily_tick,
        bank_credit_tick,
        storage_fee_tick,
        investment_tick,
        campaign_tick,
        boss_tick,
        war_genius_tick,
        achievement_tick,
    )

    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        income_tick,
        trigger=IntervalTrigger(minutes=INCOME_TICK_MINUTES),
        id="income_tick",
        name="income_tick",
        max_instances=1,
        misfire_grace_time=30,
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

    # ── Банк: кредиты (каждую минуту) ────────────────────────────────────────
    scheduler.add_job(
        bank_credit_tick,
        trigger=IntervalTrigger(minutes=1),
        id="bank_credit_tick",
        name="bank_credit_tick",
        max_instances=1,
        misfire_grace_time=10,
    )

    # ── Банк: плата за хранилище (каждую минуту) ──────────────────────────────
    scheduler.add_job(
        storage_fee_tick,
        trigger=IntervalTrigger(minutes=1),
        id="storage_fee_tick",
        name="storage_fee_tick",
        max_instances=1,
        misfire_grace_time=10,
    )

    # ── Банк: созревание вкладов (каждую минуту) ──────────────────────────────
    scheduler.add_job(
        investment_tick,
        trigger=IntervalTrigger(minutes=1),
        id="investment_tick",
        name="investment_tick",
        max_instances=1,
        misfire_grace_time=10,
    )

    # ── Походы: завершение истёкших ───────────────────────────────────────────
    scheduler.add_job(
        campaign_tick,
        trigger=IntervalTrigger(minutes=CAMPAIGN_TICK_MINUTES),
        id="campaign_tick",
        name="campaign_tick",
        max_instances=1,
        misfire_grace_time=30,
    )

    # ── Боссы: спавн и завершение ─────────────────────────────────────────────
    scheduler.add_job(
        boss_tick,
        trigger=IntervalTrigger(seconds=BOSS_TICK_SECONDS),
        id="boss_tick",
        name="boss_tick",
        max_instances=1,
        misfire_grace_time=30,
    )

    # ── Гений войны: авто-атака рейдов ───────────────────────────────────────
    scheduler.add_job(
        war_genius_tick,
        trigger=IntervalTrigger(minutes=1),
        id="war_genius_tick",
        name="war_genius_tick",
        max_instances=1,
        misfire_grace_time=30,
    )

    # ── Войны за регионы Кореи ────────────────────────────────────────────────
    scheduler.add_job(
        region_war_tick,
        trigger=IntervalTrigger(minutes=REGION_WAR_TICK_MINUTES),
        id="region_war_tick",
        name="region_war_tick",
        max_instances=1,
        misfire_grace_time=60,
    )

    # ── Достижения: авто-проверка для недавно активных игроков ──────────────
    scheduler.add_job(
        achievement_tick,
        trigger=IntervalTrigger(minutes=ACHIEVEMENT_TICK_MINUTES),
        id="achievement_tick",
        name="achievement_tick",
        max_instances=1,
        misfire_grace_time=60,
    )

    logger.info("Scheduler configured with 16 jobs")
    return scheduler