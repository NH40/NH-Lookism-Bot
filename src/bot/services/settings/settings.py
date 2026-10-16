"""Настройки уведомлений (сервис).

`users.notify_muted` — массив ВЫКЛЮЧЕННЫХ категорий пушей (`constant/settings`), пустой
по умолчанию: новая категория, добавленная позже, у всех сразу включена. Все пуши игры идут
через `notify_player()` (личный пуш) или `unmuted_ids()` (рассылка о событии на карте) —
проверка выключателя в одном месте, а не в каждом домене по-своему.
"""
from __future__ import annotations

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.settings import NOTIFY_CATEGORIES
from bot.db.models.user import User
from bot.utils.notify import notify


class UnknownCategoryError(Exception):
    pass


async def muted_categories(session: AsyncSession, user_id: int) -> set[str]:
    value = await session.scalar(select(User.notify_muted).where(User.id == user_id))
    return set(value or ())


async def is_muted(session: AsyncSession, user_id: int, category: str) -> bool:
    return bool(
        await session.scalar(select(User.id).where(User.id == user_id, User.notify_muted.any(category)))
    )


async def notify_player(
    bot: Bot,
    session: AsyncSession,
    user_id: int,
    category: str,
    text_: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    """Личный пуш, если игрок не выключил эту категорию. Best-effort, как `utils/notify`."""
    if await is_muted(session, user_id, category):
        return False
    return await notify(bot, user_id, text_, reply_markup=reply_markup)


async def toggle(session: AsyncSession, user_id: int, category: str) -> bool:
    """Переключить категорию одним атомарным UPDATE. Возвращает: включена ли теперь. Коммитит."""
    if category not in NOTIFY_CATEGORIES:
        raise UnknownCategoryError(category)
    muted = await session.scalar(
        text(
            "UPDATE users SET notify_muted = CASE WHEN :c = ANY(notify_muted) "
            "THEN array_remove(notify_muted, :c) ELSE array_append(notify_muted, :c) END "
            "WHERE id = :uid RETURNING :c = ANY(notify_muted)"
        ),
        {"c": category, "uid": user_id},
    )
    await session.commit()
    return not muted


async def set_all(session: AsyncSession, user_id: int, enabled: bool) -> None:
    """Включить или выключить все категории разом. Коммитит."""
    await session.execute(
        update(User).where(User.id == user_id).values(notify_muted=[] if enabled else list(NOTIFY_CATEGORIES))
    )
    await session.commit()
