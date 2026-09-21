from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.settings import get_settings
from bot.services.admin import is_admin


class IsAdminFilter(BaseFilter):
    """Вешается на весь `handlers/admin` роутер (родитель, не на каждый под-роутер по
    отдельности) — не-админам команды/кнопки молча не отвечают (не "недостаточно прав",
    а тишина, как для неизвестной команды), чтобы не палить сам факт существования
    админки посторонним."""

    async def __call__(self, event: Message | CallbackQuery, session: AsyncSession) -> bool:
        if event.from_user is None:
            return False
        settings = get_settings()
        return await is_admin(session, event.from_user.id, settings)
