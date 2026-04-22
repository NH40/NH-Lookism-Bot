from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionFactory
from app.services.business_service import business_service
from app.services.deck_service import deck_service
from app.services.squad_service import squad_service
from app.services.auction_service import auction_service
import logging

logger = logging.getLogger(__name__)


async def income_tick():
    async with AsyncSessionFactory() as session:
        async with session.begin():
            from app.repositories.user_repo import user_repo
            users = await user_repo.get_all_with_income(session)
            for user in users:
                try:
                    await business_service.tick_income(session, user)
                except Exception as e:
                    logger.error(f"income_tick error for {user.id}: {e}")


async def ultra_instinct_tick():
    async with AsyncSessionFactory() as session:
        async with session.begin():
            from app.repositories.user_repo import user_repo
            users = await user_repo.get_all_ui_users(session)
            for user in users:
                try:
                    if user.ui_auto_ticket:
                        await deck_service.try_get_ticket(session, user)
                    if user.ui_auto_pull and user.tickets > 0:
                        await deck_service.pull_all(session, user)
                    if user.ui_auto_recruit:
                        await _ui_recruit(session, user)
                    if user.ui_auto_train:
                        await squad_service.train(session, user)
                except Exception as e:
                    logger.error(f"ui_tick error for {user.id}: {e}")


async def _ui_recruit(session: AsyncSession, user):
    """Авто-вербовка для УИ."""
    from app.services.cooldown_service import cooldown_service
    cd_key = cooldown_service.recruit_key(user.id)
    if await cooldown_service.is_on_cooldown(cd_key):
        return
    await squad_service.recruit(session, user)


async def auction_tick():
    async with AsyncSessionFactory() as session:
        async with session.begin():
            result = await auction_service.finish_auction(session)
            if result is not None:
                if result.get("winner_id"):
                    await _notify_auction_winner(session, result)
                await auction_service.start_new_auction(session)


async def _notify_auction_winner(session: AsyncSession, result: dict):
    try:
        from app.repositories.user_repo import user_repo
        winner = await user_repo.get_by_id(session, result["winner_id"])
        if not winner or not winner.notifications_enabled:
            return
        import json
        reward = result.get("reward", "{}")
        data = json.loads(reward) if reward else {}
        from app.main import bot
        await bot.send_message(
            winner.tg_id,
            f"🏛 <b>Вы победили на аукционе!</b>\n\n"
            f"🎁 Награда получена!\n"
            f"Проверьте вашу коллекцию.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"notify auction winner error: {e}")