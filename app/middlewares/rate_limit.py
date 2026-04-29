import time
from typing import Callable, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, CallbackQuery
import logging

logger = logging.getLogger(__name__)

RATE_LIMIT = 0.5  # секунд между нажатиями


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, limit: float = RATE_LIMIT):
        self.limit = limit
        self._last_call: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id = None
        if hasattr(event, 'from_user') and event.from_user:
            user_id = event.from_user.id

        if user_id:
            now = time.time()
            last = self._last_call.get(user_id, 0)
            diff = now - last

            if diff < self.limit:
                # Для callback — просто отвечаем без алерта
                if isinstance(event, CallbackQuery):
                    try:
                        await event.answer()
                    except Exception:
                        pass
                return None

            self._last_call[user_id] = now

        return await handler(event, data)