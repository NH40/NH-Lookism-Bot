from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from redis.asyncio import Redis

from bot.cache.keys import throttle_flag


class ThrottlingMiddleware(BaseMiddleware):
    """Общий антифлуд — не даёт одному игроку слать апдейты чаще, чем раз в
    `throttle_interval_ms` (SET NX PX по Redis). Не путать с `action_lock` (правило 2) —
    тот защищает КОНКРЕТНОЕ resource-affecting действие от повторного клика на ТОЙ ЖЕ
    кнопке; это — общий предохранитель от спама текстом/кнопками вперемешку. Лишний
    апдейт молча отбрасывается — сам факт троттлинга не должен порождать ответ."""

    def __init__(self, redis: Redis, interval_ms: int) -> None:
        self._redis = redis
        self._interval_ms = interval_ms

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.successful_payment is not None:
            # См. ban_check.py/tech_mode.py — деньги уже списаны Telegram, троттлинг не
            # должен задерживать/терять начисление.
            return await handler(event, data)

        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        acquired = await self._redis.set(throttle_flag(user.id), "1", nx=True, px=self._interval_ms)
        if not acquired:
            return None

        return await handler(event, data)
