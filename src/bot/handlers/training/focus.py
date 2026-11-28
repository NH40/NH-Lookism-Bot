"""Фокус тренировки — родословная Хансу (хендлеры, 2026-11-28).

Отмеченные отряды (лагерь+ранг+школа) забирают весь охват тренировки статистов (`services/training/focus`).
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.training import CB_FOCUS_OPEN_PREFIX, CB_FOCUS_TOGGLE_PREFIX
from bot.keyboards.training import focus_menu
from bot.services.training import FocusSlotsFullError, FocusUnavailableError, focus_view, toggle_focus
from bot.texts.training import FOCUS_HINT, FOCUS_NO_ARMY, FOCUS_NOT_AVAILABLE_ALERT, FOCUS_SCREEN, FOCUS_SLOTS_FULL_ALERT
from bot.utils.safe_edit import safe_edit_text

router = Router(name="training_focus")


def _page(raw: str) -> int:
    return int(raw) if raw.isdigit() else 0


async def _show(callback: CallbackQuery, session: AsyncSession, page: int) -> None:
    try:
        view = await focus_view(session, callback.from_user.id)
    except FocusUnavailableError:
        await callback.answer(FOCUS_NOT_AVAILABLE_ALERT, show_alert=True)
        return
    await callback.answer()
    text = FOCUS_SCREEN.format(used=view.used, slots=view.slots, rows=FOCUS_HINT if view.rows else FOCUS_NO_ARMY)
    await safe_edit_text(callback.message, text, reply_markup=focus_menu(view, page))


@router.callback_query(F.data.startswith(CB_FOCUS_OPEN_PREFIX))
async def cb_focus_open(callback: CallbackQuery, session: AsyncSession) -> None:
    await _show(callback, session, _page(callback.data.removeprefix(CB_FOCUS_OPEN_PREFIX)))


@router.callback_query(F.data.startswith(CB_FOCUS_TOGGLE_PREFIX))
async def cb_focus_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    parts = callback.data.removeprefix(CB_FOCUS_TOGGLE_PREFIX).split(":", 3)
    if len(parts) != 4:
        await callback.answer()
        return
    page, camp, rank, school = parts
    try:
        await toggle_focus(session, callback.from_user.id, camp, rank, school)
    except FocusUnavailableError:
        await callback.answer(FOCUS_NOT_AVAILABLE_ALERT, show_alert=True)
        return
    except FocusSlotsFullError as e:
        await callback.answer(FOCUS_SLOTS_FULL_ALERT.format(slots=e.slots), show_alert=True)
        return
    await _show(callback, session, _page(page))
