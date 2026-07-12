import logging
from sqlalchemy import select
from app.database import AsyncSessionFactory
from app.models.user import User
from app.models.clan import Clan, ClanMember
from app.utils.formatters import fmt_num
from app.scheduler.tasks.notifications import _send_notifications

logger = logging.getLogger(__name__)


async def clan_power_reconcile_tick():
    """Периодически пересчитывает Clan.combat_power = SUM(members.combat_power).

    Обычно клан обновляется инкрементально (squad_repo.update_user_combat_power
    применяет дельту при каждом изменении силы игрока) — это дёшево, но любая
    ошибка в дельте (например, экстремальный кратковременный скачок силы одного
    игрока, упирающийся в защитный кап) накапливается в Clan.combat_power
    навсегда, так как полный пересчёт иначе делается только при вступлении/выходе
    из клана. Этот тик — страховка: раз в час чинит дрейф с нуля, per-клан
    в своей транзакции, чтобы ошибка на одном клане не блокировала остальные.
    """
    try:
        async with AsyncSessionFactory() as session:
            clan_ids = list((await session.execute(select(Clan.id))).scalars().all())

        for clan_id in clan_ids:
            try:
                async with AsyncSessionFactory() as session:
                    async with session.begin():
                        clan = await session.get(Clan, clan_id)
                        if clan:
                            from app.services.clan import clan_service
                            await clan_service.recalc_power(session, clan)
            except Exception as e:
                logger.error(f"clan_power_reconcile_tick error for clan {clan_id}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"clan_power_reconcile_tick error: {e}", exc_info=True)


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

        # Step 2: batch-fetch tg_ids for every involved clan in one query
        from app.bot_instance import get_bot
        bot = get_bot()

        all_clan_ids = {
            cid for outcome in notif_queue for cid in (outcome["winner_id"], outcome["loser_id"])
        }
        clan_tg_map: dict[int, list[int]] = {cid: [] for cid in all_clan_ids}
        async with AsyncSessionFactory() as session:
            rows = await session.execute(
                select(ClanMember.clan_id, User.tg_id)
                .join(User, User.id == ClanMember.user_id)
                .where(
                    ClanMember.clan_id.in_(all_clan_ids),
                    User.notifications_enabled == True,
                    User.notif_clan_war == True,
                )
            )
            for clan_id, tg_id in rows.all():
                clan_tg_map[clan_id].append(tg_id)
        # ← сессия закрыта; дальше только сеть, без удержания соединения с БД

        if not bot:
            return

        for outcome in notif_queue:
            war_type_str = "вооружения" if outcome["war_type"] == "power" else "богатств"
            for clan_id, reward, is_winner in [
                (outcome["winner_id"], outcome["winner_reward"], True),
                (outcome["loser_id"], outcome["loser_reward"], False),
            ]:
                result_str = "🏆 Победа!" if is_winner else "❌ Поражение"
                war_text = (
                    f"⚔️ <b>Война {war_type_str} завершена!</b>\n\n"
                    f"{result_str}\n"
                    f"💰 В казну: +{fmt_num(reward)} NHCoin"
                )
                await _send_notifications(bot, clan_tg_map.get(clan_id, []), war_text)

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

        all_clan_ids = {
            cid
            for outcome in notif_queue
            for cid in (outcome.get("winner_clan_id"), outcome.get("prev_owner_clan_id"))
            if cid
        }
        clan_tg_map: dict[int, list[int]] = {cid: [] for cid in all_clan_ids}
        async with AsyncSessionFactory() as session:
            rows = await session.execute(
                select(ClanMember.clan_id, User.tg_id)
                .join(User, User.id == ClanMember.user_id)
                .where(ClanMember.clan_id.in_(all_clan_ids))
            )
            for clan_id, tg_id in rows.all():
                clan_tg_map[clan_id].append(tg_id)
        # ← сессия закрыта; дальше только сеть, без удержания соединения с БД

        if not bot:
            return

        for outcome in notif_queue:
            winner_id = outcome.get("winner_clan_id")
            region_emoji = outcome.get("region_emoji", "🗺")
            region_name = outcome.get("region_name", "регион")
            winner_score = outcome.get("winner_score", 0)

            if not winner_id:
                continue

            tg_ids = clan_tg_map.get(winner_id, [])
            region_transferred = outcome.get("region_transferred", False)
            prev_id = outcome.get("prev_owner_clan_id")

            if region_transferred:
                win_text = (
                    f"🏆 <b>Регион захвачен!</b>\n\n"
                    f"{region_emoji} <b>{region_name}</b> теперь принадлежит вашему клану!\n"
                    f"Счёт: <b>{winner_score}</b> ОА  →  +{int(winner_score * 1.5)} в казну\n"
                    f"Бонусы региона активированы."
                )
            else:
                win_text = (
                    f"🏆 <b>Победа в войне за регион!</b>\n\n"
                    f"{region_emoji} <b>{region_name}</b> теперь принадлежит вашему клану!\n"
                    f"Счёт: <b>{winner_score}</b> ОА в казну.\n"
                    f"Бонусы региона активированы."
                )
            await _send_notifications(bot, tg_ids, win_text)

            if prev_id and prev_id != winner_id:
                loss_text = (
                    f"😔 <b>Регион потерян!</b>\n\n"
                    f"{region_emoji} <b>{region_name}</b> захвачен другим кланом.\n"
                    f"Соберите силы и отвоюйте его!"
                )
                await _send_notifications(bot, clan_tg_map.get(prev_id, []), loss_text)

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
