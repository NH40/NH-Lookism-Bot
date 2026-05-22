import logging
from sqlalchemy import select
from app.database import AsyncSessionFactory
from app.services.auction_service import auction_service, AUCTION_TIERS
from app.scheduler.tasks.notifications import _send_notifications, _get_bot

logger = logging.getLogger(__name__)


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
                    await _notify_auction_started(new_auction.tier, tier_name, tier_emoji)
    except Exception as e:
        logger.error(f"auction_start_tick error: {e}", exc_info=True)


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

        from app.models.user import User
        async with AsyncSessionFactory() as session:
            tg_ids = list((await session.execute(
                select(User.tg_id).where(
                    User.notifications_enabled == True,
                    User.notif_auction == True,
                )
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

        from app.models.user import User
        async with AsyncSessionFactory() as session:
            tg_ids = list((await session.execute(
                select(User.tg_id).where(
                    User.notifications_enabled == True,
                    User.notif_auction == True,
                )
            )).scalars())
        await _send_notifications(bot, tg_ids, text)
    except Exception as e:
        logger.error(f"notify_round_end error: {e}")


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

        from app.models.user import User
        winner_tg_id = winner["tg_id"] if winner else None
        async with AsyncSessionFactory() as session:
            tg_ids = list((await session.execute(
                select(User.tg_id).where(
                    User.notifications_enabled == True,
                    User.notif_auction == True,
                )
            )).scalars())
        tg_ids = [tid for tid in tg_ids if tid != winner_tg_id]
        await _send_notifications(bot, tg_ids, text)
    except Exception as e:
        logger.error(f"notify_auction_end error: {e}")
