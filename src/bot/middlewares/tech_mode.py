from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from redis.asyncio import Redis

from bot.cache.keys import tech_mode_flag
from bot.db.repositories.user import get_by_id

TECH_MODE_TEXT = "🛠 Бот на техническом перерыве. Загляните чуть позже."


class TechModeMiddleware(BaseMiddleware):
    """Единая точка блокировки всех апдейтов кроме админских, когда включён техрежим.
    Флаг лежит в Redis, чтобы включать/выключать мгновенно без деплоя (правило 9)."""

    def __init__(self, redis: Redis, admin_ids: set[int]) -> None:
        self._redis = redis
        self._admin_ids = admin_ids

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.successful_payment is not None:
            return await handler(event, data)

        user = data.get("event_from_user")
        if user and user.id in self._admin_ids:
            return await handler(event, data)

        if not await self._redis.get(tech_mode_flag()):
            return await handler(event, data)

        # Техрежим реально включён и это не супер-админ из конфига — лишь тут стоит
        # похода в БД за доп. админами (User.is_admin), тот же принцип, что в UAP:
        # техрежим почти всегда выключен, так что этот путь почти никогда не выполняется.
        if user is not None:
            session = data.get("session")
            if session is not None:
                db_user = await get_by_id(session, user.id)
                if db_user is not None and db_user.is_admin:
                    return await handler(event, data)

        if isinstance(event, Message):
            await event.answer(TECH_MODE_TEXT)
        elif isinstance(event, CallbackQuery):
            await event.answer(TECH_MODE_TEXT, show_alert=True)
        return None
