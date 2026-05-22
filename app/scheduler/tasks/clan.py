import logging
from sqlalchemy import select
from app.database import AsyncSessionFactory
from app.models.user import User
from app.utils.formatters import fmt_num
from app.scheduler.tasks.notifications import _send_notifications

logger = logging.getLogger(__name__)


async def clan_war_tick():
    """Завершает просроченные войны кланов и выдаёт награды."""
    try:
        # Step 1: commit treasury updates; collect primitive data for notifications
        notif_queue = []
        async with AsyncSessionFactory() as session:
            async with session.begin():
                from app.services.clan import clan_service
                finished = await clan_service.finish_expired_wars(session)
                for outcome in finished:
                    if not outcome.get("ok"):
                        continue
                    notif_queue.append(outcome)

        if not notif_queue:
            return

        # Step 2: send notifications outside the transaction (treasury already committed)
        from app.bot_instance import get_bot
        from app.models.clan import ClanMember
        bot = get_bot()

        async with AsyncSessionFactory() as session:
            for outcome in notif_queue:
                war_type_str = "вооружения" if outcome["war_type"] == "power" else "богатств"
                for clan_id, reward, is_winner in [
                    (outcome["winner_id"], outcome["winner_reward"], True),
                    (outcome["loser_id"], outcome["loser_reward"], False),
                ]:
                    tg_ids_r = await session.execute(
                        select(User.tg_id)
                        .join(ClanMember, ClanMember.user_id == User.id)
                        .where(
                            ClanMember.clan_id == clan_id,
                            User.notifications_enabled == True,
                            User.notif_clan_war == True,
                        )
                    )
                    clan_tg_ids = list(tg_ids_r.scalars())
                    result_str = "🏆 Победа!" if is_winner else "❌ Поражение"
                    war_text = (
                        f"⚔️ <b>Война {war_type_str} завершена!</b>\n\n"
                        f"{result_str}\n"
                        f"💰 В казну: +{fmt_num(reward)} NHCoin"
                    )
                    if bot:
                        await _send_notifications(bot, clan_tg_ids, war_text)

    except Exception as e:
        logger.error(f"clan_war_tick error: {e}", exc_info=True)


async def clan_auction_tick():
    """Каждую минуту — завершает истёкшие клановые аукционы и выдаёт награды.

    Каждый аукцион обрабатывается в своей транзакции, чтобы сбой одного
    не откатывал награды остальных.
    """
    try:
        from app.services.clan import clan_service

        # Шаг 1: собираем ID истёкших аукционов (read-only)
        async with AsyncSessionFactory() as session:
            auction_ids = await clan_service.get_expired_auction_ids(session)

        # Шаг 2: завершаем каждый аукцион в отдельной транзакции
        for auction_id in auction_ids:
            try:
                async with AsyncSessionFactory() as session:
                    async with session.begin():
                        await clan_service.finish_auction_by_id(session, auction_id)
            except Exception as e:
                logger.error(
                    f"clan_auction_tick error for auction {auction_id}: {e}",
                    exc_info=True,
                )
    except Exception as e:
        logger.error(f"clan_auction_tick error: {e}", exc_info=True)
