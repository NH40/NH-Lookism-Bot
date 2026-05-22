import logging
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionFactory
from app.models.user import User
from app.services.deck_service import deck_service
from app.services.squad_service import squad_service

logger = logging.getLogger(__name__)


async def ultra_instinct_tick():
    async with AsyncSessionFactory() as session:
        user_ids = list((await session.execute(
            select(User.id).where(
                or_(User.ultra_instinct == True, User.ui_is_donat == True, User.donat_ui_potion == True)
            )
        )).scalars())

    for user_id in user_ids:
        try:
            async with AsyncSessionFactory() as session:
                async with session.begin():
                    user = await session.get(User, user_id)
                    if not user:
                        continue
                    if user.ui_auto_ticket:
                        await deck_service.try_get_ticket(session, user)
                    if user.ui_auto_pull and user.tickets > 0:
                        await deck_service.pull_all(session, user)
                    if user.ui_auto_recruit:
                        await _ui_recruit(session, user)
                    if user.ui_auto_train:
                        await squad_service.train(session, user)
                    if user.ui_auto_potion:
                        await _ui_auto_potion(session, user)
        except Exception as e:
            logger.error(f"ui_tick error for user {user_id}: {e}")


async def _ui_recruit(session: AsyncSession, user):
    from app.services.cooldown_service import cooldown_service
    cd_key = cooldown_service.recruit_key(user.id)
    if await cooldown_service.is_on_cooldown(cd_key):
        return
    await squad_service.recruit(session, user)


async def _ui_auto_potion(session: AsyncSession, user):
    from app.services.potion_service import potion_service
    await potion_service.buy_missing(session, user)
