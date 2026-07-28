import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.client.default import DefaultBotProperties
from app.bot_instance import set_bot
from app.config import settings
from app.database import init_db
from app.middlewares.db_session import DbSessionMiddleware
from app.middlewares.user_loader import UserLoaderMiddleware
from app.scheduler.setup import setup_scheduler
from app.handlers import common, attack, business, raid, squad, skills, titles, shop, auction, settings as settings_handler, admin, guide, black_market, donate
from app.handlers.campaigns import router as campaigns_router
from app.handlers.bosses import router as bosses_router
from app.handlers import training
from app.handlers.cards import router as cards_router
from app.handlers.bank import router as bank_router
from aiohttp import TCPConnector
from app.middlewares.network_error import NetworkErrorMiddleware
from app.middlewares.rate_limit import RateLimitMiddleware
from app.middlewares.network_error import NetworkErrorMiddleware
from app.handlers import market
from app.handlers import quests
from app.handlers import horse_shop
from app.handlers.clan import router as clan_router
from app.handlers import fame as fame_handler
from app.handlers import quick_menu

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

bot: Bot = None

HEARTBEAT_PATH = "/app/heartbeat"
HEARTBEAT_INTERVAL_SECONDS = 15


async def _heartbeat_loop():
    """Пишет текущее время в файл каждые 15с, пока крутится event loop.
    Если процесс зависнет (event loop заблокирован где-то синхронно или
    в дедлоке), этот цикл тоже перестанет обновлять файл — именно на
    "протух ли heartbeat" смотрит HEALTHCHECK в docker-compose, чтобы
    отличить реально зависший процесс от просто тихого (нет сообщений)."""
    import time
    while True:
        try:
            with open(HEARTBEAT_PATH, "w") as f:
                f.write(str(int(time.time())))
        except Exception:
            logger.warning("heartbeat write failed", exc_info=True)
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)


async def main():
    global bot

    logger.info("Initializing database...")
    await init_db()

    logger.info("Initializing cities...")
    await init_cities()

    logger.info("Initializing fame fragments...")
    await init_fame()

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    set_bot(bot)

    storage = RedisStorage.from_url(settings.redis_url)
    dp = Dispatcher(storage=storage)

    dp.message.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())
    dp.message.middleware(UserLoaderMiddleware())
    dp.callback_query.middleware(UserLoaderMiddleware())
    dp.message.middleware(NetworkErrorMiddleware())
    dp.callback_query.middleware(NetworkErrorMiddleware())
    dp.message.middleware(RateLimitMiddleware())
    dp.callback_query.middleware(RateLimitMiddleware())

    # pre_checkout_query — нужен DbSession для записи (UserLoader не нужен, ответ быстрый)
    dp.pre_checkout_query.middleware(DbSessionMiddleware())

    # quick_menu — ПЕРВЫЙ роутер: точный текст reply-кнопки быстрого меню
    # должен перехватывать нажатие раньше любого активного FSM-хэндлера
    # (например, ввода суммы) в остальных роутерах ниже.
    dp.include_router(quick_menu.router)

    dp.include_router(common.router)
    dp.include_router(attack.router)
    
    dp.include_router(business.router)
    dp.include_router(squad.router)
    dp.include_router(cards_router)
    dp.include_router(skills.router)
    dp.include_router(titles.router)
    dp.include_router(shop.router)
    dp.include_router(auction.router)
    dp.include_router(training.router)
    dp.include_router(raid.router)
    dp.include_router(market.router)
    dp.include_router(horse_shop.router)
    dp.include_router(clan_router)
    dp.include_router(quests.router)
    dp.include_router(campaigns_router)
    dp.include_router(bosses_router)
    dp.include_router(bank_router)
    dp.include_router(settings_handler.router)
    dp.include_router(guide.router)
    dp.include_router(black_market.router)
    dp.include_router(donate.router)
    dp.include_router(fame_handler.router)

    dp.include_router(admin.router)

    scheduler = setup_scheduler()
    scheduler.start()
    logger.info("Scheduler started")

    heartbeat_task = asyncio.create_task(_heartbeat_loop())

    logger.info("Starting bot polling...")
    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            timeout=10,
            retry_after=5,
        )
    finally:
        heartbeat_task.cancel()
        scheduler.shutdown()
        await bot.session.close()
        logger.info("Bot stopped")


async def init_fame():
    from app.database import AsyncSessionFactory
    from app.services.fame_service import fame_service

    async with AsyncSessionFactory() as session:
        async with session.begin():
            await fame_service.seed_fragments(session)


async def init_cities():
    from app.database import AsyncSessionFactory
    from app.models.city import City
    from app.data.cities import COUNTRIES, GANG_CITY_TYPES, CITY_NAMES_BY_COUNTRY
    from sqlalchemy import select, func

    async with AsyncSessionFactory() as session:
        async with session.begin():
            count = await session.scalar(
                select(func.count(City.id)).where(
                    City.phase == "gang", City.country.isnot(None)
                )
            )
            if count and count > 0:
                logger.info(f"Gang cities already initialized: {count}")
                return

            logger.info("Creating gang cities...")
            total = 0
            for c in COUNTRIES:
                names = CITY_NAMES_BY_COUNTRY.get(c.code, [])
                name_idx = 0
                for city_type in GANG_CITY_TYPES:
                    for i in range(10):
                        name = names[name_idx % len(names)] if names else f"Город {name_idx}"
                        name_idx += 1
                        city = City(
                            country=c.code,
                            phase="gang",
                            type_id=city_type.type_id,
                            name=name,
                            total_districts=city_type.total_districts,
                        )
                        session.add(city)
                        total += 1

            logger.info(f"Created {total} gang cities")


if __name__ == "__main__":
    asyncio.run(main())