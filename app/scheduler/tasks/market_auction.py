"""Завершение истёкших аукционов биржи: выдача лота победителю, оплата продавцу минус комиссия."""
import logging
from app.database import AsyncSessionFactory
from app.services.market_auction_service import market_auction_service
from app.services.market_notify import notify_market_sale, notify_market_purchase

logger = logging.getLogger(__name__)


async def _notify_no_bids(seller, item_label: str) -> None:
    if not seller or not seller.notifications_enabled or not getattr(seller, "notif_market_sell", True):
        return
    try:
        from app.bot_instance import get_bot
        bot = get_bot()
        if not bot:
            return
        await bot.send_message(
            seller.tg_id,
            f"📭 <b>Аукцион завершён без ставок</b>\n\n{item_label} возвращён вам.",
            parse_mode="HTML",
        )
    except Exception:
        pass


async def market_auction_tick():
    """Каждую минуту — завершает истёкшие аукционы биржи.

    Каждый аукцион обрабатывается в своей транзакции, чтобы сбой одного
    не откатывал результат остальных (по образцу clan_auction_tick).
    """
    try:
        # Шаг 1: собираем ID истёкших аукционов (read-only)
        async with AsyncSessionFactory() as session:
            auction_ids = await market_auction_service.get_expired_auction_ids(session)

        # Шаг 2: разрешаем каждый аукцион в отдельной транзакции
        for auction_id in auction_ids:
            try:
                event = None
                async with AsyncSessionFactory() as session:
                    async with session.begin():
                        event = await market_auction_service.resolve_expired_by_id(session, auction_id)

                if not event:
                    continue

                if event["event"] == "no_bids":
                    await _notify_no_bids(event.get("seller"), event["item_label"])
                elif event["event"] == "won":
                    winner = event.get("winner")
                    seller = event.get("seller")
                    if seller:
                        await notify_market_sale(
                            seller, event["item_label"], event["amount"], event["price"], event["resource"]
                        )
                    if winner:
                        await notify_market_purchase(
                            winner, event["item_label"], event["amount"], event["price"], event["resource"]
                        )
            except Exception as e:
                logger.error(f"market_auction_tick error for auction {auction_id}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"market_auction_tick error: {e}", exc_info=True)
