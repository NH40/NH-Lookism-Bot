"""Пуши второй стороне из API Mini App — те же функции и тексты, что у хендлеров бота.

Один лениво создаваемый `Bot` (HTML-режим, как в `bot/main.py`) на процесс, закрывается в
lifespan приложения. Всё best-effort: сбой пуша никогда не валит запрос API.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import session_factory
from bot.config.settings import get_settings
from bot.services.settings import notify_player

log = logging.getLogger(__name__)

_bot: Bot | None = None


def get_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(token=get_settings().bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    return _bot


async def close_bot() -> None:
    global _bot
    if _bot is not None:
        await _bot.session.close()
        _bot = None


async def push(user_id: int, category: str, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    """`notify_player` бота (учитывает mute категории) на отдельной короткой сессии."""
    try:
        async with session_factory() as session:
            await notify_player(get_bot(), session, user_id, category, text, reply_markup=reply_markup)
    except Exception:
        log.exception("api push failed (user %s)", user_id)


async def push_many(user_ids, category: str, text: str) -> None:
    for uid in user_ids:
        await push(uid, category, text)


async def with_bot_session(fn: Callable[[Bot, AsyncSession], Awaitable[Any]]) -> None:
    """Выполнить функцию бота вида `fn(bot, session)` (например `send_deal_pushes`), best-effort."""
    try:
        async with session_factory() as session:
            await fn(get_bot(), session)
    except Exception:
        log.exception("api push failed")


async def push_poker(event, skip_user: int | None = None) -> None:
    """`push_event` покер-хендлера: итог раздачи и свежий экран стола всем за столом."""
    from bot.handlers.poker import push_event

    try:
        await push_event(get_bot(), session_factory, event, skip_user=skip_user)
    except Exception:
        log.exception("api poker push failed")
