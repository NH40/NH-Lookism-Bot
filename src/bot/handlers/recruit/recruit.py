"""Вербовка — статисты (по влиянию, КД 20 минут) и уникальные персонажи (за тикеты) (хендлеры).

Уникальные персонажи — TODO (см. `services/recruit`). Пока только вербовка статистов —
команда `/recruit`, до появления настоящего меню «Карта».
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.recruit import CB_RECRUIT_EXTRA, CB_RECRUIT_OPEN
from bot.db.repositories.user import get_by_id
from bot.keyboards.recruit import recruit_menu
from bot.services.extra import get_army_stats
from bot.services.recruit import RecruitOnCooldownError, recruit_extra
from bot.texts.common import render_army_block
from bot.texts.profile import NOT_ONBOARDED
from bot.texts.recruit import RECRUIT_COOLDOWN, RECRUIT_MENU_HEADER, RECRUIT_RESULT
from bot.utils.formatting import format_countdown, format_number

router = Router(name="recruit")


async def show_recruit_menu(message: Message, session: AsyncSession, user_id: int) -> None:
    """Публичная функция домена (не `_show`) — переиспользуется главным меню профиля
    (`handlers/common.cb_recruit_open`, кнопка "🎯 Вербовка")."""
    stats = await get_army_stats(session, user_id)
    army_block = render_army_block(
        total_quantity=stats.total_quantity, total_power=stats.total_power, by_rank=stats.by_rank
    )
    await message.answer(RECRUIT_MENU_HEADER.format(army_block=army_block), reply_markup=recruit_menu())


@router.message(Command("recruit"))
async def cmd_recruit(message: Message, session: AsyncSession) -> None:
    user = await get_by_id(session, message.from_user.id)
    if user is None or user.city_id is None:
        await message.answer(NOT_ONBOARDED)
        return
    await show_recruit_menu(message, session, user.id)


@router.callback_query(F.data == CB_RECRUIT_OPEN)
async def cb_recruit_open(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_by_id(session, callback.from_user.id)
    if user is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    await callback.answer()
    await show_recruit_menu(callback.message, session, user.id)


@router.callback_query(F.data == CB_RECRUIT_EXTRA)
async def cb_recruit_extra(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    user = await get_by_id(session, callback.from_user.id)
    if user is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return

    try:
        result = await recruit_extra(session, redis, user.id, user.phase)
    except RecruitOnCooldownError as exc:
        # Popup-алерт не поддерживает HTML (см. CLAUDE.md UAP) — этот текст без тегов.
        await callback.answer(
            RECRUIT_COOLDOWN.format(countdown=format_countdown(exc.retry_after_seconds)),
            show_alert=True,
        )
        return

    await callback.answer()
    await callback.message.answer(RECRUIT_RESULT.format(rank=result.rank, power=format_number(result.power)))
    await show_recruit_menu(callback.message, session, user.id)
