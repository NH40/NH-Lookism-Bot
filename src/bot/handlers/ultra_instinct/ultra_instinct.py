"""Ультра инстинкт — экран настроек (хендлеры). Каждое действие включается и выключается отдельно."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.ultra_instinct import (
    CB_ULTRA_ACTION_PREFIX,
    CB_ULTRA_BOSS_PREFIX,
    CB_ULTRA_LOSS_PREFIX,
    CB_ULTRA_OPEN,
)
from bot.keyboards.ultra_instinct import ultra_menu
from bot.services.ultra_instinct import (
    MaxLossError,
    UltraUnavailableError,
    get_view,
    set_max_loss,
    toggle_action,
    toggle_boss,
)
from bot.texts.ultra_instinct import BOSS_BLOCK, BOSS_LOCKED, NOT_AVAILABLE_ALERT, ULTRA_SCREEN
from bot.utils.safe_edit import safe_edit_text

router = Router(name="ultra_instinct")


async def _show(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        view = await get_view(session, callback.from_user.id)
    except UltraUnavailableError:
        await callback.answer(NOT_AVAILABLE_ALERT, show_alert=True)
        return
    await callback.answer()
    boss_block = BOSS_BLOCK.format(max_loss=view.max_loss) if view.boss_available else BOSS_LOCKED
    await safe_edit_text(callback.message, ULTRA_SCREEN.format(boss_block=boss_block), reply_markup=ultra_menu(view))


@router.callback_query(F.data == CB_ULTRA_OPEN)
async def cb_ultra_open(callback: CallbackQuery, session: AsyncSession) -> None:
    await _show(callback, session)


async def _apply(callback: CallbackQuery, session: AsyncSession, action) -> None:
    """Настройка → перерисовка. Запись идёт под блокировкой строки игрока, повторный клик безопасен."""
    try:
        await action
    except (UltraUnavailableError, MaxLossError):
        await session.rollback()
        await callback.answer(NOT_AVAILABLE_ALERT, show_alert=True)
        return
    await _show(callback, session)


@router.callback_query(F.data.startswith(CB_ULTRA_ACTION_PREFIX))
async def cb_ultra_action(callback: CallbackQuery, session: AsyncSession) -> None:
    code = callback.data.removeprefix(CB_ULTRA_ACTION_PREFIX)
    await _apply(callback, session, toggle_action(session, callback.from_user.id, code))


@router.callback_query(F.data.startswith(CB_ULTRA_BOSS_PREFIX))
async def cb_ultra_boss(callback: CallbackQuery, session: AsyncSession) -> None:
    code = callback.data.removeprefix(CB_ULTRA_BOSS_PREFIX)
    await _apply(callback, session, toggle_boss(session, callback.from_user.id, code))


@router.callback_query(F.data.startswith(CB_ULTRA_LOSS_PREFIX))
async def cb_ultra_loss(callback: CallbackQuery, session: AsyncSession) -> None:
    raw = callback.data.removeprefix(CB_ULTRA_LOSS_PREFIX)
    await _apply(callback, session, set_max_loss(session, callback.from_user.id, int(raw) if raw.isdigit() else -1))
