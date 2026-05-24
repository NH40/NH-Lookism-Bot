import logging
from app.database import AsyncSessionFactory
from app.services.business_service import business_service

logger = logging.getLogger(__name__)


async def income_tick():
    async with AsyncSessionFactory() as session:
        async with session.begin():
            from app.repositories.user_repo import user_repo
            from sqlalchemy import select, or_
            from app.models.user import User
            # Берём всех: у кого есть доход ИЛИ пассивный доход от кругов
            result = await session.execute(
                select(User).where(
                    or_(User.income_per_minute > 0, User.circ_passive_income > 0)
                )
            )
            users = result.scalars().all()
            from app.services.quest_service import quest_service
            for user in users:
                try:
                    earned = 0
                    if user.income_per_minute > 0:
                        earned = await business_service.tick_income(session, user)
                    # Пассивный доход от круговых донатов: NHCoin/час → /60 за тик (1 мин)
                    circ_income = getattr(user, "circ_passive_income", 0)
                    if circ_income > 0:
                        per_tick = circ_income // 60
                        if per_tick > 0:
                            user.nh_coins += per_tick
                            earned = (earned or 0) + per_tick
                    if earned and earned > 0:
                        await quest_service.add_progress(session, user, "income", amount=int(earned))
                except Exception as e:
                    logger.error(f"income_tick error for {user.id}: {e}")
