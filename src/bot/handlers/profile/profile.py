"""Экран «Профиль» — статистика, характеристики, мастерство, выбор уникальной техники/пути/родословной/гениальности/пробуждения, кнопка удаления банды (хендлеры).

`show_profile()` — публичная функция домена (не `_show`), переиспользуется
`handlers/start` (см. CLAUDE.md UAP, "/start у существующего игрока открывает профиль" —
тот же переход портирован сюда).
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.settings import get_settings
from bot.keyboards.profile import profile_menu
from bot.services.profile import get_profile
from bot.texts.profile import NOT_ONBOARDED, PHASE_LABELS, PROFILE_CARD
from bot.utils.mini_app import resolve_mini_app_base_url

router = Router(name="profile")


async def show_profile(message: Message, session: AsyncSession, user_id: int) -> None:
    profile = await get_profile(session, user_id)
    if profile is None or not profile.is_onboarded:
        await message.answer(NOT_ONBOARDED)
        return

    settings = get_settings()
    mini_app_url = resolve_mini_app_base_url(settings.mini_app_url, message.chat.type)
    await message.answer(
        PROFILE_CARD.format(
            display_name=profile.display_name or "—",
            username=f"@{profile.username}" if profile.username else "—",
            gang_name=profile.gang_name or "—",
            country=profile.country.name if profile.country else "—",
            city=profile.city.name if profile.city else "—",
            phase_label=PHASE_LABELS.get(profile.phase, profile.phase),
        ),
        reply_markup=profile_menu(mini_app_url=mini_app_url),
    )


@router.message(Command("profile"))
async def cmd_profile(message: Message, session: AsyncSession) -> None:
    await show_profile(message, session, message.from_user.id)
