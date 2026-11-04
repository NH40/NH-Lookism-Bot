"""Управление рангами статистов — родословная Самдака (хендлеры).

Пользователь 2026-11-04: Самдак — контрпик капа тренировки. Игрок сам решает, когда статисту переходить на
следующий ранг: может запретить переход или перевести вручную всех, кто дошёл до обычного капа.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.training import CB_RANKS_LOCK_PREFIX, CB_RANKS_OPEN, CB_RANKS_PROMOTE_PREFIX
from bot.db.repositories.user import get_by_id
from bot.keyboards.training import ranks_menu
from bot.services.training import (
    NothingToPromoteError,
    RankHoldUnavailableError,
    promote_rank,
    rank_control,
    toggle_rank_lock,
)
from bot.texts.profile import NOT_ONBOARDED
from bot.texts.training import (
    RANKS_NO_ARMY,
    RANKS_NOT_AVAILABLE_ALERT,
    RANKS_NOTHING_TO_PROMOTE_ALERT,
    RANKS_PROMOTED_ALERT,
    RANKS_ROW,
    RANKS_SCREEN,
)
from bot.utils.formatting import format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="training_ranks")


async def _show(callback: CallbackQuery, session: AsyncSession, alert: str | None = None) -> None:
    user = await get_by_id(session, callback.from_user.id)
    if user is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    try:
        rows = await rank_control(session, user.id, user.phase)
    except RankHoldUnavailableError:
        await callback.answer(RANKS_NOT_AVAILABLE_ALERT, show_alert=True)
        return
    await callback.answer(alert or "")
    lines = "\n".join(
        RANKS_ROW.format(
            mark="🔒" if r.locked else "🔓", rank=r.rank, quantity=format_number(r.quantity), cap=r.cap, ready=format_number(r.ready)
        )
        for r in rows
    ) or RANKS_NO_ARMY
    await safe_edit_text(callback.message, RANKS_SCREEN.format(rows=lines), reply_markup=ranks_menu(rows))


@router.callback_query(F.data == CB_RANKS_OPEN)
async def cb_ranks_open(callback: CallbackQuery, session: AsyncSession) -> None:
    await _show(callback, session)


@router.callback_query(F.data.startswith(CB_RANKS_LOCK_PREFIX))
async def cb_ranks_lock(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        await toggle_rank_lock(session, callback.from_user.id, callback.data.removeprefix(CB_RANKS_LOCK_PREFIX))
    except RankHoldUnavailableError:
        await session.rollback()
        await callback.answer(RANKS_NOT_AVAILABLE_ALERT, show_alert=True)
        return
    await _show(callback, session)


@router.callback_query(F.data.startswith(CB_RANKS_PROMOTE_PREFIX))
async def cb_ranks_promote(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_by_id(session, callback.from_user.id)
    if user is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    try:
        moved = await promote_rank(session, user.id, callback.data.removeprefix(CB_RANKS_PROMOTE_PREFIX), user.phase)
    except RankHoldUnavailableError:
        await callback.answer(RANKS_NOT_AVAILABLE_ALERT, show_alert=True)
        return
    except NothingToPromoteError:
        await callback.answer(RANKS_NOTHING_TO_PROMOTE_ALERT, show_alert=True)
        return
    await _show(callback, session, RANKS_PROMOTED_ALERT.format(count=format_number(moved)))
