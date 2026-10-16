"""Бета-режим: пока включён, не-админы перед любым действием вводят кодовое слово.

Срочный запрос пользователя 2026-09-30. Outer-middleware на `message` и `callback_query`
(работает на ВСЕ апдейты, даже если ни один хендлер не совпал) — стоит после
`DbSessionMiddleware` (нужна сессия для проверки `User.is_admin`) и после техрежима
(техрежим строже — закрывает бота целиком). Логика — `services/admin/beta.py`.

Порядок проверок — от дешёвых к дорогим, тот же принцип, что у `TechModeMiddleware`:
оплата (деньги уже списаны — не блокировать) → конфиг-админ (память) → бета выключена
(один GET в Redis, почти всегда) → игрок уже допущен (SISMEMBER) → доп. админ из БД
(только когда бета реально включена и игрок не допущен).

Недопущенный игрок: текстовое сообщение — это попытка ввести код (верно → допуск,
иначе подсказка); нажатие кнопки — алерт с просьбой прислать код. До хендлеров такие
апдейты не доходят.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from redis.asyncio import Redis

from bot.db.repositories.user import get_by_id
from bot.services.admin import beta
from bot.texts.admin import (
    BETA_GATE_ALERT,
    BETA_GATE_GRANTED,
    BETA_GATE_LOCKED,
    BETA_GATE_PROMPT,
    BETA_GATE_WRONG,
)


class BetaGateMiddleware(BaseMiddleware):
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
        if user is None or user.id in self._admin_ids:
            return await handler(event, data)

        state = await beta.get_state(self._redis)
        if state is None or await beta.is_allowed(self._redis, state, user.id):
            return await handler(event, data)

        session = data.get("session")
        if session is not None:
            db_user = await get_by_id(session, user.id)
            if db_user is not None and (db_user.is_admin or db_user.admin_role):
                return await handler(event, data)

        if isinstance(event, CallbackQuery):
            await event.answer(BETA_GATE_ALERT, show_alert=True)
            return None

        if isinstance(event, Message):
            text = event.text or ""
            # Команды (/start и т.п.) — не попытка ввести код, их не считаем в лимит попыток.
            if not text or text.startswith("/"):
                await event.answer(BETA_GATE_PROMPT)
                return None
            result = await beta.try_enter(self._redis, state, user.id, text)
            if result is beta.EntryResult.GRANTED:
                await event.answer(BETA_GATE_GRANTED)
            elif result is beta.EntryResult.LOCKED:
                await event.answer(BETA_GATE_LOCKED)
            else:
                await event.answer(BETA_GATE_WRONG)
        return None
