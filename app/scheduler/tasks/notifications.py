import asyncio
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


async def _get_bot():
    from app.bot_instance import get_bot
    return get_bot()
