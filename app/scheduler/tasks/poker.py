"""Тик покерных столов: старт раздач по таймеру ожидания, авто-действия по таймауту хода."""
import logging
from app.database import AsyncSessionFactory
from app.services.bank.casino.poker_service import poker_service
from app.services.bank.casino.poker_notify import notify_event

logger = logging.getLogger(__name__)


async def poker_tick():
    events = []
    async with AsyncSessionFactory() as session:
        async with session.begin():
            try:
                events = await poker_service.tick(session)
            except Exception as e:
                logger.error(f"poker_tick error: {e}", exc_info=True)
                events = []

        # Уведомления отправляем в отдельной сессии ПОСЛЕ коммита —
        # notify_event только читает пользователей, транзакция уже закрыта.
        if events:
            bot_instance = None
            try:
                from app.bot_instance import get_bot
                bot_instance = get_bot()
            except Exception:
                pass

            if bot_instance:
                for event in events:
                    try:
                        await notify_event(bot_instance, session, event)
                    except Exception as e:
                        logger.warning(f"poker_tick notify error: {e}")
