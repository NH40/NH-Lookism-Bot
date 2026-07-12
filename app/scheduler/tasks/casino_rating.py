"""Еженедельный сброс и награждение рейтинга казино (каждый понедельник 00:00 UTC)."""
import logging
from app.database import AsyncSessionFactory
from app.services.bank.casino.rating_service import casino_rating_service
from app.constants.bank import CASINO_RATING_REWARDS
from app.utils.formatters import fmt_num

logger = logging.getLogger(__name__)

_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


async def casino_rating_tick():
    rewarded: list[dict] = []

    async with AsyncSessionFactory() as session:
        async with session.begin():
            try:
                rewarded = await casino_rating_service.reset_and_reward(session)
            except Exception as e:
                logger.error(f"casino_rating_tick error: {e}", exc_info=True)
                rewarded = []

    if not rewarded:
        return

    bot_instance = None
    try:
        from app.bot_instance import get_bot
        bot_instance = get_bot()
    except Exception:
        pass

    if not bot_instance:
        return

    for entry in rewarded:
        medal = _MEDALS.get(entry["rank"], "")
        reward = entry["reward"]
        text = (
            f"🏆 <b>Итоги недели казино!</b>\n\n"
            f"{medal} Вы заняли {entry['rank']} место с прибылью +{fmt_num(entry['net_won'])} NHCoin!\n\n"
            f"Награда: {fmt_num(reward.get('nh_coins', 0))} NHCoin + {reward.get('tickets', 0)} 🎟"
        )
        try:
            await bot_instance.send_message(entry["tg_id"], text, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"casino_rating_tick notif error tg_id={entry['tg_id']}: {e}")
