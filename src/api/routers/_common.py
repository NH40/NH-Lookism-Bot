"""Общие хелперы роутеров карты/банды/уников: проверка регистрации, КД из Redis, тексты ошибок
без эмодзи и HTML (в Mini App тосты — plain text)."""
from __future__ import annotations

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.settings import get_settings
from bot.db.models.user import User
from bot.db.repositories.user import get_by_id
from bot.utils.formatting import format_countdown

NOT_ONBOARDED_MSG = "Сначала пройди регистрацию в боте — набери /start."

_LEADING_NOISE = re.compile(r"^[^\w]+", re.UNICODE)
_TAGS = re.compile(r"<[^>]+>")


def plain_lines(lines) -> list[str]:
    """Строки журнала боя (HTML бота) → простой текст для Mini App."""
    return [_TAGS.sub("", line).strip() for line in lines]


def clean_label(text: str) -> str:
    """Подпись из бота -> без ведущих эмодзи и HTML-тегов."""
    return _LEADING_NOISE.sub("", _TAGS.sub("", text)).strip()


async def require_user(session: AsyncSession, user_id: int, *, need_city: bool = True) -> User:
    user = await get_by_id(session, user_id)
    if user is None or (need_city and user.city_id is None):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_ONBOARDED_MSG)
    return user


async def ttl_seconds(redis: Redis, key: str) -> int:
    """Остаток КД по ключу Redis (0 — КД нет)."""
    return max(0, int(await redis.ttl(key)))


def cooldown_text(prefix: str, seconds: int) -> str:
    return f"{prefix} ещё на кулдауне — попробуй через {format_countdown(seconds)}."


def bad(text: str) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, text)


@asynccontextmanager
async def telegram_bot() -> AsyncIterator[Bot]:
    """Короткоживущий Bot для пуша второй стороне (защитнику вызова, императору трона) —
    тот же HTML-режим, что у бота; HTTP-сессия закрывается на выходе."""
    bot = Bot(token=get_settings().bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        yield bot
    finally:
        await bot.session.close()
