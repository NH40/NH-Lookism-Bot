from __future__ import annotations

import asyncio
import logging
import time

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.services.admin.live_config import refresh_loop as refresh_live_config
from bot.cache.redis_client import make_redis, make_redis_pool
from bot.config.game import CHALLENGE_SWEEP_INTERVAL_SECONDS
from bot.config.settings import get_settings
from bot.db.session import make_engine, make_session_factory
from bot.handlers import get_routers
from bot.services.donate import import_lbp1
from bot.handlers.district import send_pvp_reports
from bot.handlers.empire import send_war_reports
from bot.logging_setup import setup_logging
from bot.middlewares.ban_check import BanCheckMiddleware
from bot.middlewares.beta_gate import BetaGateMiddleware
from bot.middlewares.command_state_reset import CommandStateResetMiddleware
from bot.middlewares.db_session import DbSessionMiddleware
from bot.middlewares.tech_mode import TechModeMiddleware
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.services.district import resolve_expired
from bot.services.empire import resolve_expired_wars
from bot.config.mastery import MASTERY_SWEEP_INTERVAL_SECONDS
from bot.handlers.mastery import send_quest_pushes
from bot.config.event import EVENT_TICK_SECONDS
from bot.handlers.event import send_spawn_pushes
from bot.handlers.school import school_push_text
from bot.handlers.unique_technique import teacher_push_text
from bot.services.event import spawn_due
from bot.services.ultra_instinct import ULTRA_INSTINCT_TICK_SECONDS, run_once as run_ultra_instinct
from bot.services.activity import purge as purge_activity
from bot.services.contract import purge as purge_contracts
from bot.services.potion import renew_auto as renew_potions
from bot.handlers.potion import send_auto_pushes as send_potion_pushes
from bot.config.potion import POTION_AUTO_SWEEP_SECONDS
from bot.config.poker import POKER_TICK_SECONDS
from bot.config.exchange import EXCHANGE_SWEEP_SECONDS
from bot.services.exchange import expire_trades, finish_auctions
from bot.handlers.exchange import send_deal_pushes
from bot.services.poker import tick as poker_tick
from bot.handlers.poker import push_event as push_poker_event
from bot.services.mastery import activate_due, check_breakthroughs
from bot.config.top import TOP_POWER_REFRESH_SECONDS
from bot.services.top import refresh_powers, sweep_seasons
from bot.services.cooldown import sweep as sweep_cooldown_pushes

log = logging.getLogger(__name__)

HEARTBEAT_PATH = "/app/heartbeat"
HEARTBEAT_INTERVAL_SECONDS = 15

# Фоновые задачи — обычные asyncio.create_task с sleep, тем же паттерном, что в Universe
# Anime Planet (не Celery/APScheduler, см. config/scheduler/scheduler.py — "открытый
# вопрос"). Каждая новая — только под механику, которая физически НЕ может быть ленивой,
# не "про запас":
# - `_heartbeat_loop` — не игровая механика, сигнал для HEALTHCHECK/autoheal
#   (docker-compose.yml): unix-время в файл, чтобы отличать зависший event loop.
# - `_challenge_sweep_loop` — просроченные PvP-вызовы: если защитник так и не зайдёт в
#   бота, без фонового прохода бой не случился бы никогда, а нападающий не узнал бы итог.


async def _mastery_sweep_loop(bot: Bot, session_factory) -> None:
    """Раз в минуту активирует наступившие этапы цепочки «Преодоление стены» (задание
    приходит в случайный момент 1–24 ч — без фонового прохода игрок узнал бы о нём, только
    открыв экран) и шлёт пуш. Падение одного прохода не останавливает цикл."""
    while True:
        try:
            await check_breakthroughs(session_factory)  # прорыв сделан → пошло ожидание задания
            activated = await activate_due(session_factory)
            if activated:
                async with session_factory() as session:
                    await send_quest_pushes(bot, session, activated)
        except Exception:
            log.exception("Mastery sweep failed")
        await asyncio.sleep(MASTERY_SWEEP_INTERVAL_SECONDS)


async def _challenge_sweep_loop(
    bot: Bot, session_factory: async_sessionmaker[AsyncSession], redis: Redis
) -> None:
    while True:
        try:
            outcomes = await resolve_expired(session_factory, redis)
            if outcomes:
                async with session_factory() as session:
                    for outcome in outcomes:
                        await send_pvp_reports(bot, session, outcome)
        except Exception:
            log.exception("Challenge sweep failed")
        # Тот же проход — неявки на войну императоров (не принял вызов — поражение без боя).
        try:
            wars = await resolve_expired_wars(session_factory, redis)
            if wars:
                async with session_factory() as session:
                    for war in wars:
                        await send_war_reports(bot, session, war)
        except Exception:
            log.exception("Emperor war sweep failed")
        await asyncio.sleep(CHALLENGE_SWEEP_INTERVAL_SECONDS)


def _teacher_push_text(event) -> str | None:
    """Пуш об учителе на карте: учитель техник или учитель статистов."""
    return teacher_push_text(event) or school_push_text(event)


async def _events_loop(bot: Bot, session_factory: async_sessionmaker[AsyncSession]) -> None:
    """События на карте (боссы, учителя): появляются случайно раз в `EVENT_TICK_SECONDS`
    (физически не может быть ленивым — событие должно появиться и прийти пушем, даже если
    никто не открывает карту). Пуши — отдельной задачей, чтобы рассылка не держала проход."""
    tick = 0
    while True:
        tick += 1
        try:
            if tick % 12 == 0:  # раз в час — старые записи журнала и истёкшие контракты
                await purge_activity(session_factory)
                await purge_contracts(session_factory)
            spawned = await spawn_due(session_factory)
            if spawned:
                task = asyncio.create_task(send_spawn_pushes(bot, session_factory, spawned, _teacher_push_text))
                _BACKGROUND.add(task)
                task.add_done_callback(_BACKGROUND.discard)
        except Exception:
            log.exception("Events loop failed")
        await asyncio.sleep(EVENT_TICK_SECONDS)


async def _potion_loop(bot: Bot, session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Авто-зелья гения медицины: продлеваются в момент окончания, даже если игрок не заходит
    (эффект нужен в бою, который может начать противник). Раз в `POTION_AUTO_SWEEP_SECONDS`."""
    while True:
        try:
            results = await renew_potions(session_factory)
            if results:
                async with session_factory() as session:
                    await send_potion_pushes(bot, session, results)
        except Exception:
            log.exception("Potion sweep failed")
        await asyncio.sleep(POTION_AUTO_SWEEP_SECONDS)


async def _poker_loop(bot: Bot, session_factory: async_sessionmaker[AsyncSession]) -> None:
    """PvP-покер: старт столов по истечении ожидания и авто-ход по таймауту (иначе игрок,
    ушедший из бота посреди раздачи, повесил бы стол навсегда)."""
    while True:
        try:
            for event in await poker_tick(session_factory):
                await push_poker_event(bot, session_factory, event)
        except Exception:
            log.exception("Poker tick failed")
        await asyncio.sleep(POKER_TICK_SECONDS)


async def _exchange_loop(bot: Bot, session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Биржа: итоги истёкших аукционов и возврат истёкших предложений обмена — предмет должен
    дойти до победителя или вернуться владельцу, даже если никто не открывает биржу."""
    while True:
        try:
            deals = await finish_auctions(session_factory) + await expire_trades(session_factory)
            if deals:
                async with session_factory() as session:
                    await send_deal_pushes(bot, session, deals)
        except Exception:
            log.exception("Exchange sweep failed")
        await asyncio.sleep(EXCHANGE_SWEEP_SECONDS)


async def _ultra_instinct_loop(session_factory: async_sessionmaker[AsyncSession], redis: Redis) -> None:
    """Автоматика Ультра инстинкта (родословная Ямадзаки): вербовка, тренировки, крутка —
    за игрока, теми же сервисами и с теми же КД. Не может быть ленивой: смысл способности —
    чтобы действия шли, даже когда игрок не в боте."""
    while True:
        try:
            await run_ultra_instinct(session_factory, redis)
        except Exception:
            log.exception("Ultra instinct loop failed")
        await asyncio.sleep(ULTRA_INSTINCT_TICK_SECONDS)


async def _top_loop(bot: Bot, session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Топ: снимок мощи заходивших за сутки и выплата наград по итогу сезона Battle Pass
    (итог месяца должен прийти, даже если никто не открыл топ)."""
    while True:
        try:
            await refresh_powers(session_factory)
            await sweep_seasons(bot, session_factory)
        except Exception:
            log.exception("Top loop failed")
        await asyncio.sleep(TOP_POWER_REFRESH_SECONDS)


COOLDOWN_PUSH_TICK_SECONDS = 30


async def _cooldown_loop(bot: Bot, session_factory: async_sessionmaker[AsyncSession], redis: Redis) -> None:
    """Пуши «готово» по окончании КД атаки и тренировок (`services/cooldown`): у Redis-ключа КД нет
    события «истёк», поэтому очередь с временем окончания разбирается раз в полминуты."""
    while True:
        try:
            await sweep_cooldown_pushes(bot, session_factory, redis)
        except Exception:
            log.exception("Cooldown push sweep failed")
        await asyncio.sleep(COOLDOWN_PUSH_TICK_SECONDS)


async def _arkhangel_loop(bot: Bot, session_factory: async_sessionmaker[AsyncSession], redis: Redis) -> None:
    """Абсолют Архангел: раз в час доля часового дохода (`services/absolute.arkhangel`)."""
    from bot.services.absolute import ARKHANGEL_SWEEP_SECONDS, arkhangel_sweep

    while True:
        try:
            await arkhangel_sweep(bot, session_factory, redis)
        except Exception:
            log.exception("Arkhangel sweep failed")
        await asyncio.sleep(ARKHANGEL_SWEEP_SECONDS)


# Ссылки на фоновые задачи — иначе сборщик мусора может убить их до завершения.
_BACKGROUND: set[asyncio.Task] = set()


async def _heartbeat_loop() -> None:
    while True:
        try:
            with open(HEARTBEAT_PATH, "w") as f:
                # time.time() — эпоха, ровно то, с чем сравнивает `date +%s` в
                # healthcheck (docker-compose.yml) — не монотонные часы event loop'а.
                f.write(str(int(time.time())))
        except OSError:
            log.warning("Heartbeat write failed", exc_info=True)
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    engine = make_engine(settings)
    session_factory = make_session_factory(engine)
    try:  # настройки админа «на лету» — в память
        from bot.services.admin.live_config import load as load_live_config

        await load_live_config(session_factory)
    except Exception:
        log.exception("Live config load failed")
    if settings.lbp1_database_url:
        # Перенос доната LBP 1.3 — один раз (дальше только дозачисление новым игрокам).
        try:
            await import_lbp1(session_factory, settings.lbp1_database_url)
        except Exception:
            log.exception("LBP 1.3 donate import failed")

    redis_pool = make_redis_pool(settings.redis_url)
    redis = make_redis(redis_pool)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    # FSM-состояния переживают рестарт бота — хранятся в Redis, а не в памяти процесса.
    dp = Dispatcher(storage=RedisStorage(redis))

    throttle_mw = ThrottlingMiddleware(redis, settings.throttle_interval_ms)
    db_mw = DbSessionMiddleware(session_factory)
    tech_mw = TechModeMiddleware(redis, settings.admin_ids)
    beta_mw = BetaGateMiddleware(redis, settings.admin_ids)
    ban_mw = BanCheckMiddleware()
    command_state_reset_mw = CommandStateResetMiddleware()

    # Порядок важен: throttle_mw — самый внешний, отсекает спам ДО открытия сессии БД.
    # db_mw — следующий, чтобы session была доступна tech_mw/ban_mw. Outer-мидлвари
    # работают на все апдейты, даже если ни один хендлер не совпал по фильтрам (важно
    # для антифлуда/техрежима/бана) — см. CLAUDE.md UAP, "Антифлуд и fallback".
    for observer in (dp.message, dp.callback_query):
        observer.outer_middleware(throttle_mw)
        observer.outer_middleware(db_mw)
        observer.outer_middleware(tech_mw)
        # Бета-режим — после техрежима (тот строже) и после db (нужна сессия для is_admin).
        observer.outer_middleware(beta_mw)
        observer.outer_middleware(ban_mw)
    # Только Message — у callback_query команд не бывает.
    dp.message.outer_middleware(command_state_reset_mw)

    dp.include_routers(*get_routers())

    background = [
        asyncio.create_task(_heartbeat_loop()),
        asyncio.create_task(_challenge_sweep_loop(bot, session_factory, redis)),
        asyncio.create_task(_mastery_sweep_loop(bot, session_factory)),
        asyncio.create_task(_events_loop(bot, session_factory)),
        asyncio.create_task(_ultra_instinct_loop(session_factory, redis)),
        asyncio.create_task(_potion_loop(bot, session_factory)),
        asyncio.create_task(_poker_loop(bot, session_factory)),
        asyncio.create_task(_exchange_loop(bot, session_factory)),
        asyncio.create_task(_top_loop(bot, session_factory)),
        asyncio.create_task(_cooldown_loop(bot, session_factory, redis)),
        asyncio.create_task(_arkhangel_loop(bot, session_factory, redis)),
        asyncio.create_task(refresh_live_config(session_factory)),
    ]

    try:
        log.info("Starting bot polling")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, redis=redis, session_factory=session_factory)
    finally:
        for task in background:
            task.cancel()
        for task in background:
            try:
                await task
            except asyncio.CancelledError:
                pass
        await bot.session.close()
        await engine.dispose()
        await redis.aclose()
        await redis_pool.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
