"""
Ежедневные бонусы от круговых донатов.

circ_daily_districts (Архангел круг 10):
  Каждый день игроку начисляется NHCoin-бонус эквивалентный владению
  N районов на протяжении всего дня. Базовая ставка — 500 NHCoin за район в день.
"""
import logging
from sqlalchemy import select
from app.database import AsyncSessionFactory
from app.models.user import User

logger = logging.getLogger(__name__)

# 500 NHCoin за каждый «свободный» район в день
DISTRICT_DAILY_COIN_RATE = 500


async def daily_tick():
    """
    Ежедневный тик — начисляет NHCoin за circ_daily_districts (Архангел).
    Запускается один раз в сутки (в 00:00 UTC).
    """
    async with AsyncSessionFactory() as session:
        async with session.begin():
            result = await session.execute(
                select(User).where(User.circ_daily_districts > 0)
            )
            users = result.scalars().all()
            count = 0
            for user in users:
                try:
                    districts = getattr(user, "circ_daily_districts", 0)
                    if districts > 0:
                        bonus = districts * DISTRICT_DAILY_COIN_RATE
                        user.nh_coins += bonus
                        count += 1
                        logger.info(
                            f"daily_tick: user {user.id} +{bonus} NHCoin "
                            f"({districts} районов × {DISTRICT_DAILY_COIN_RATE})"
                        )
                except Exception as e:
                    logger.error(f"daily_tick error for user {user.id}: {e}")
            if count:
                logger.info(f"daily_tick: обработано {count} пользователей с circ_daily_districts")
