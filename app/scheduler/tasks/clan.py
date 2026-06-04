import logging
from sqlalchemy import select
from app.database import AsyncSessionFactory
from app.models.user import User
from app.models.clan import ClanMember
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


async def region_war_tick():
    """Завершает просроченные войны за регионы Кореи и передаёт владение."""
    try:
        notif_queue = []
        async with AsyncSessionFactory() as session:
            async with session.begin():
                from app.services.clan import clan_service
                outcomes = await clan_service.finish_expired_region_wars(session)
                for o in outcomes:
                    if o.get("ok"):
                        notif_queue.append(o)

        if not notif_queue:
            return

        from app.bot_instance import get_bot
        bot = get_bot()

        async with AsyncSessionFactory() as session:
            for outcome in notif_queue:
                winner_id = outcome.get("winner_clan_id")
                region_emoji = outcome.get("region_emoji", "🗺")
                region_name = outcome.get("region_name", "регион")

                if not winner_id:
                    # Никто не набрал порог — рассылаем всем участникам войны
                    continue

                tg_ids_r = await session.execute(
                    select(User.tg_id)
                    .join(ClanMember, ClanMember.user_id == User.id)
                    .where(ClanMember.clan_id == winner_id)
                )
                tg_ids = list(tg_ids_r.scalars())
                text = (
                    f"🏆 <b>Победа в войне за регион!</b>\n\n"
                    f"{region_emoji} <b>{region_name}</b> теперь принадлежит вашему клану!\n"
                    f"Бонусы региона активированы."
                )
                if bot:
                    await _send_notifications(bot, tg_ids, text)

                # Уведомляем бывшего владельца если был
                prev_id = outcome.get("prev_owner_clan_id")
                if prev_id and prev_id != winner_id:
                    prev_tg_r = await session.execute(
                        select(User.tg_id)
                        .join(ClanMember, ClanMember.user_id == User.id)
                        .where(ClanMember.clan_id == prev_id)
                    )
                    prev_tg_ids = list(prev_tg_r.scalars())
                    loss_text = (
                        f"😔 <b>Регион потерян!</b>\n\n"
                        f"{region_emoji} <b>{region_name}</b> захвачен другим кланом.\n"
                        f"Соберите силы и отвоюйте его!"
                    )
                    if bot:
                        await _send_notifications(bot, prev_tg_ids, loss_text)

    except Exception as e:
        logger.error(f"region_war_tick error: {e}", exc_info=True)


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
