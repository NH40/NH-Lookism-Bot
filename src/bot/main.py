from __future__ import annotations

import asyncio
import logging
import time

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from bot.cache.redis_client import make_redis, make_redis_pool
from bot.config.settings import get_settings
from bot.db.session import make_engine, make_session_factory
from bot.handlers import get_routers
from bot.logging_setup import setup_logging
from bot.middlewares.ban_check import BanCheckMiddleware
from bot.middlewares.command_state_reset import CommandStateResetMiddleware
from bot.middlewares.db_session import DbSessionMiddleware
from bot.middlewares.tech_mode import TechModeMiddleware
from bot.middlewares.throttling import ThrottlingMiddleware

log = logging.getLogger(__name__)

HEARTBEAT_PATH = "/app/heartbeat"
HEARTBEAT_INTERVAL_SECONDS = 15

# TODO: как только появится первая ИГРОВАЯ механика, которая физически не может быть
# ленивой (см. config/scheduler/scheduler.py — "открытый вопрос" про APScheduler vs
# sweep-луп), заводить под неё отдельный asyncio.create_task с sleep, тем же
# паттерном, что в Universe Anime Planet — не Celery/APScheduler, и не заранее "про
# запас". `_heartbeat_loop` ниже — единственное исключение: не игровая механика, а
# инфраструктурный сигнал для HEALTHCHECK/autoheal в docker-compose.yml (перенесён из
# 1.0, тот же приём — пишет unix-время в файл, чтобы healthcheck отличал зависший
# event loop от процесса, который просто не получает апдейтов).


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
        observer.outer_middleware(ban_mw)
    # Только Message — у callback_query команд не бывает.
    dp.message.outer_middleware(command_state_reset_mw)

    dp.include_routers(*get_routers())

    heartbeat_task = asyncio.create_task(_heartbeat_loop())

    try:
        log.info("Starting bot polling")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, redis=redis, session_factory=session_factory)
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        await bot.session.close()
        await engine.dispose()
        await redis.aclose()
        await redis_pool.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
