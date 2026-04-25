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
from app.handlers import common, attack, business, squad, deck, skills, titles, shop, auction, settings as settings_handler, admin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

bot: Bot = None


async def main():
    global bot

    # Инициализация БД
    logger.info("Initializing database...")
    await init_db()

    # Инициализация городов
    logger.info("Initializing cities...")
    await init_cities()

    # Бот
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    set_bot(bot)

    # FSM Storage — Redis
    storage = RedisStorage.from_url(settings.redis_url)

    # Диспетчер
    dp = Dispatcher(storage=storage)

    # Middlewares
    dp.message.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())
    dp.message.middleware(UserLoaderMiddleware())
    dp.callback_query.middleware(UserLoaderMiddleware())
    
    # Роутеры
    dp.include_router(common.router)
    dp.include_router(attack.router)
    dp.include_router(business.router)
    dp.include_router(squad.router)
    dp.include_router(deck.router)
    dp.include_router(skills.router)
    dp.include_router(titles.router)
    dp.include_router(shop.router)
    dp.include_router(auction.router)
    dp.include_router(settings_handler.router)
    dp.include_router(admin.router)

    # Планировщик
    scheduler = setup_scheduler()
    scheduler.start()
    logger.info("Scheduler started")

    # Запуск
    logger.info("Starting bot polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await bot.session.close()
        logger.info("Bot stopped")


async def init_cities():
    """Инициализирует города в БД если их нет."""
    from app.database import AsyncSessionFactory
    from app.models.city import City
    from app.data.cities import SECTORS, CITY_TYPES, CITY_NAMES_BY_SECTOR
    from sqlalchemy import select, func

    async with AsyncSessionFactory() as session:
        async with session.begin():
            count = await session.scalar(select(func.count(City.id)))
            if count and count > 0:
                logger.info(f"Cities already initialized: {count}")
                return

            logger.info("Creating cities...")
            total = 0
            for sector in SECTORS:
                names = CITY_NAMES_BY_SECTOR.get(sector, [])
                name_idx = 0
                for phase in ["gang", "king", "fist"]:
                    for city_type in CITY_TYPES:
                        for i in range(10):
                            name = names[name_idx % len(names)] if names else f"Город {name_idx}"
                            name_idx += 1
                            city = City(
                                sector=sector,
                                phase=phase,
                                type_id=city_type.type_id,
                                name=f"{name} {city_type.type_id}-{i+1}",
                                total_districts=city_type.total_districts,
                            )
                            session.add(city)
                            total += 1

            logger.info(f"Created {total} cities")


if __name__ == "__main__":
    asyncio.run(main())