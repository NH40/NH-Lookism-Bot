"""Заморозка банды за долг по кредиту (пользователь 2026-11-14: «блок всего, доход в долг»).

Флаг — Redis `bank:frozen:{id}`, его ставит фоновый проход банков (`services/bank.sweep`) и снимает погашение.
Замороженному доступны только экраны кредитов (`bank:*`) и ввод суммы погашения; всё остальное — алерт/сообщение
с кнопкой «Мои кредиты». Оплата доната (`successful_payment`) проходит всегда — деньги уже списаны Telegram.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from redis.asyncio import Redis

from bot.constant.bank import FROZEN_ALLOWED_CALLBACKS, key_frozen
from bot.keyboards.bank import frozen_menu
from bot.states.bank import BankStates
from bot.texts.bank import FROZEN_ALERT, FROZEN_MESSAGE


class BankFreezeMiddleware(BaseMiddleware):
    def __init__(self, redis: Redis, admin_ids: set[int]) -> None:
        self._redis = redis
        self._admin_ids = admin_ids

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None or user.id in self._admin_ids:
            return await handler(event, data)
        if isinstance(event, Message) and event.successful_payment is not None:
            return await handler(event, data)
        if not await self._redis.exists(key_frozen(user.id)):
            return await handler(event, data)
        if isinstance(event, CallbackQuery) and (event.data or "").startswith(FROZEN_ALLOWED_CALLBACKS):
            return await handler(event, data)
        if isinstance(event, Message) and data.get("raw_state") == BankStates.repay_amount.state:
            return await handler(event, data)
        if isinstance(event, CallbackQuery):
            await event.answer(FROZEN_ALERT, show_alert=True)
        elif isinstance(event, Message):
            await event.answer(FROZEN_MESSAGE, reply_markup=frozen_menu())
        return None
