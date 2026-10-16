"""Админка: общие помощники хендлеров разделов."""
from __future__ import annotations

from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.admin import roles
from bot.texts.admin import NO_RIGHTS_ALERT


async def guard(callback: CallbackQuery, session: AsyncSession, section: str) -> bool:
    """Есть ли у админа право на раздел; нет — алерт (кнопку и так не видно, это страховка
    от старых сообщений и смены роли)."""
    if await roles.can(session, callback.from_user.id, section):
        return True
    await callback.answer(NO_RIGHTS_ALERT, show_alert=True)
    return False


def parse_id(data: str, prefix: str) -> int | None:
    raw = data.removeprefix(prefix).split(":", 1)[0]
    return int(raw) if raw.isdigit() else None
