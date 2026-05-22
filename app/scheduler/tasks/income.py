import logging
from app.database import AsyncSessionFactory
from app.services.business_service import business_service

logger = logging.getLogger(__name__)


async def income_tick():
    async with AsyncSessionFactory() as session:
        async with session.begin():
            from app.repositories.user_repo import user_repo
            users = await user_repo.get_all_with_income(session)
            from app.services.quest_service import quest_service
            for user in users:
                try:
                    earned = await business_service.tick_income(session, user)
                    if earned and earned > 0:
                        await quest_service.add_progress(session, user, "income", amount=int(earned))
                except Exception as e:
                    logger.error(f"income_tick error for {user.id}: {e}")
