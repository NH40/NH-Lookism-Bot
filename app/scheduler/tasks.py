import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionFactory
from app.models.user import User
from app.services.business_service import business_service
from app.services.deck_service import deck_service
from app.services.squad_service import squad_service
from app.services.auction_service import auction_service, AUCTION_TIERS
from app.utils.formatters import fmt_num

import logging

logger = logging.getLogger(__name__)

# Semaphore caps concurrent Telegram sends — stays within the 30 msg/s global limit.
_NOTIF_SEM = asyncio.Semaphore(20)


async def _send_notifications(bot, tg_ids: list[int], text: str) -> None:
    """Send `text` to all `tg_ids` concurrently (rate-limited by semaphore)."""
    if not tg_ids:
        return

    async def _one(tg_id: int) -> None:
        async with _NOTIF_SEM:
            try:
                await bot.send_message(tg_id, text, parse_mode="HTML")
            except Exception:
                pass

    await asyncio.gather(*[_one(tid) for tid in tg_ids])


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


async def ultra_instinct_tick():
    from sqlalchemy import or_
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


async def auction_round_tick():
    """Каждые 30 сек — обрабатываем текущий раунд аукциона."""
    try:
        async with AsyncSessionFactory() as session:
            async with session.begin():
                result = await auction_service.tick(session)
                if result is None:
                    return
                event = result.get("event")
                if event == "round_end":
                    await _notify_round_end(result)
                elif event == "auction_end":
                    await _notify_auction_end(result)
    except Exception as e:
        logger.error(f"auction_round_tick error: {e}", exc_info=True)


async def auction_start_tick():
    """Каждые 15 мин — запускаем новый аукцион если пауза прошла."""
    try:
        async with AsyncSessionFactory() as session:
            async with session.begin():
                active = await auction_service.get_active_auction(session)
                if active:
                    return

                new_auction = await auction_service.start_new_auction(session)
                if new_auction:
                    tier_cfg = AUCTION_TIERS.get(new_auction.tier, {})
                    tier_name = tier_cfg.get("name", "")
                    tier_emoji = tier_cfg.get("emoji", "🏛")
                    logger.info(
                        f"New auction started: {tier_name} (tier {new_auction.tier})"
                    )
                    # Уведомляем всех о новом аукционе
                    await _notify_auction_started(new_auction.tier, tier_name, tier_emoji)
    except Exception as e:
        logger.error(f"auction_start_tick error: {e}", exc_info=True)


async def _get_bot():
    from app.bot_instance import get_bot
    return get_bot()


async def _notify_auction_started(tier: int, tier_name: str, tier_emoji: str):
    """Уведомляем всех игроков о начале нового аукциона."""
    try:
        bot = await _get_bot()
        if not bot:
            logger.error("notify_auction_started: bot is None")
            return

        cfg = AUCTION_TIERS.get(tier, {})
        reward_type = cfg.get("reward_type", "")
        reward_hint = {
            "coins": "💰 Монеты NHCoin",
            "potion": "🧪 Зелье",
            "character": "🎴 Персонаж",
        }.get(reward_type, "Приз")

        min_bid = cfg.get("min_bid", 0)
        rounds  = cfg.get("rounds", 2)

        text = (
            f"{tier_emoji} <b>Новый аукцион начался!</b>\n\n"
            f"Тир: <b>{tier_name}</b>\n"
            f"🎁 Награда: {reward_hint}\n"
            f"💰 Мин. ставка: {min_bid:,} NHCoin\n"
            f"🔄 Раундов: {rounds}\n\n"
            f"Открой аукцион чтобы сделать ставку!"
        )

        from sqlalchemy import select
        from app.models.user import User
        async with AsyncSessionFactory() as session:
            tg_ids = list((await session.execute(
                select(User.tg_id).where(User.notifications_enabled == True)
            )).scalars())
        await _send_notifications(bot, tg_ids, text)
    except Exception as e:
        logger.error(f"notify_auction_started error: {e}")


async def _fmt_reward(lot) -> str:
    if not lot:
        return "Награда"
    import json
    try:
        data = json.loads(lot.reward_data)
        if lot.reward_type == "coins":
            return f"💰 {data['coins']:,} NHCoin"
        elif lot.reward_type == "potion":
            return f"🧪 {data.get('name', 'Зелье')}"
        elif lot.reward_type == "character":
            from app.data.characters import RANK_EMOJI
            emoji = RANK_EMOJI.get(data.get("rank", ""), "❓")
            return f"{emoji} {data.get('character', '?')}"
    except Exception:
        pass
    return "Награда"


async def _notify_round_end(result: dict):
    try:
        bot = await _get_bot()
        if not bot:
            logger.error("notify_round_end: bot is None")
            return

        winner     = result.get("winner")
        tier_emoji = result["tier_emoji"]
        tier_name  = result["tier_name"]
        round_num  = result["round"]
        total      = result["total_rounds"]
        next_round = result["next_round"]
        reward_str = await _fmt_reward(result.get("lot"))

        winner_line = (
            f"👑 {winner['name']} — {winner['bid']:,} NHCoin"
            if winner else "Ставок не было"
        )

        text = (
            f"{tier_emoji} <b>Аукцион {tier_name} — Раунд {round_num}/{total}</b>\n\n"
            f"🎁 Лот: {reward_str}\n"
            f"Победитель раунда: {winner_line}\n\n"
            f"➡️ Раунд {next_round} уже начался!"
        )

        from sqlalchemy import select
        from app.models.user import User
        async with AsyncSessionFactory() as session:
            tg_ids = list((await session.execute(
                select(User.tg_id).where(User.notifications_enabled == True)
            )).scalars())
        await _send_notifications(bot, tg_ids, text)
    except Exception as e:
        logger.error(f"notify_round_end error: {e}")

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
                        .where(ClanMember.clan_id == clan_id)
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
    """Каждую минуту — завершает истёкшие клановые аукционы и выдаёт награды."""
    try:
        async with AsyncSessionFactory() as session:
            async with session.begin():
                from app.services.clan import clan_service
                await clan_service.finish_expired_auctions(session)
    except Exception as e:
        logger.error(f"clan_auction_tick error: {e}", exc_info=True)

async def _notify_auction_end(result: dict):
    try:
        bot = await _get_bot()
        if not bot:
            logger.error("notify_auction_end: bot is None")
            return

        winner     = result.get("winner")
        tier_emoji = result["tier_emoji"]
        tier_name  = result["tier_name"]
        reward_str = await _fmt_reward(result.get("lot"))

        winner_line = (
            f"👑 <b>{winner['name']}</b> — {winner['bid']:,} NHCoin"
            if winner else "Ставок не было"
        )

        text = (
            f"{tier_emoji} <b>Аукцион {tier_name} завершён!</b>\n\n"
            f"🎁 Лот: {reward_str}\n"
            f"Победитель: {winner_line}\n\n"
            f"🏛 Следующий аукцион через 10-20 минут"
        )

        # Победителю отдельное сообщение
        if winner and winner.get("notifications"):
            try:
                await bot.send_message(
                    winner["tg_id"],
                    f"🎉 <b>Вы победили на аукционе!</b>\n\n"
                    f"🎁 {reward_str} уже у вас!\n"
                    f"Потрачено: {winner['bid']:,} NHCoin",
                    parse_mode="HTML",
                )
            except Exception:
                pass

        from sqlalchemy import select
        from app.models.user import User
        winner_tg_id = winner["tg_id"] if winner else None
        async with AsyncSessionFactory() as session:
            tg_ids = list((await session.execute(
                select(User.tg_id).where(User.notifications_enabled == True)
            )).scalars())
        tg_ids = [tid for tid in tg_ids if tid != winner_tg_id]
        await _send_notifications(bot, tg_ids, text)
    except Exception as e:
        logger.error(f"notify_auction_end error: {e}")