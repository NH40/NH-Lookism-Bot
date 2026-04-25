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
    from app.services.cooldown_service import cooldown_service
    cd_key = cooldown_service.recruit_key(user.id)
    if await cooldown_service.is_on_cooldown(cd_key):
        return
    await squad_service.recruit(session, user)


async def auction_round_tick():
    """Каждые 30 сек — обрабатываем текущий раунд аукциона."""
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


async def auction_start_tick():
    """Каждые 15 мин — запускаем новый аукцион если пауза прошла."""
    async with AsyncSessionFactory() as session:
        async with session.begin():
            active = await auction_service.get_active_auction(session)
            if active:
                return  # уже идёт

            new_auction = await auction_service.start_new_auction(session)
            if new_auction:
                tier_name = auction_service.AUCTION_TIERS.get(
                    new_auction.tier, {}
                ).get("name", "")
                logger.info(f"New auction started: {tier_name} (tier {new_auction.tier})")


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
        from app.main import bot

        winner = result.get("winner")
        tier_emoji = result["tier_emoji"]
        tier_name = result["tier_name"]
        round_num = result["round"]
        total = result["total_rounds"]
        next_round = result["next_round"]
        reward_str = await _fmt_reward(result.get("lot"))

        winner_line = (
            f"👑 {winner['name']} — {winner['bid']:,} NHCoin"
            if winner else "Ставок не было"
        )

        text = (
            f"{tier_emoji} <b>Аукцион {tier_name} — Раунд {round_num}/{total}</b>\n\n"
            f"🎁 Лот: {reward_str}\n"
            f"Победитель: {winner_line}\n\n"
            f"➡️ Раунд {next_round} начался!"
        )

        async with AsyncSessionFactory() as session:
            async with session.begin():
                from sqlalchemy import select
                from app.models.user import User
                users_r = await session.execute(
                    select(User).where(User.notifications_enabled == True)
                )
                for u in users_r.scalars().all():
                    try:
                        await bot.send_message(u.tg_id, text, parse_mode="HTML")
                    except Exception:
                        pass
    except Exception as e:
        logger.error(f"notify_round_end error: {e}")


async def _notify_auction_end(result: dict):
    try:
        from app.main import bot

        winner = result.get("winner")
        tier_emoji = result["tier_emoji"]
        tier_name = result["tier_name"]
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

        # Победителю отдельно
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

        async with AsyncSessionFactory() as session:
            async with session.begin():
                from sqlalchemy import select
                from app.models.user import User
                users_r = await session.execute(
                    select(User).where(User.notifications_enabled == True)
                )
                for u in users_r.scalars().all():
                    if winner and u.tg_id == winner["tg_id"]:
                        continue
                    try:
                        await bot.send_message(u.tg_id, text, parse_mode="HTML")
                    except Exception:
                        pass
    except Exception as e:
        logger.error(f"notify_auction_end error: {e}")