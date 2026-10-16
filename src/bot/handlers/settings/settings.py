"""Настройки (хендлеры): удаление банды (перенесено из профиля 2026-10-01) и выключатели
всех пушей игры (пользователь 2026-10-03, `services/settings`)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.common import CB_MENU_SETTINGS
from bot.constant.settings import CB_NOTIFY_ALL_OFF, CB_NOTIFY_ALL_ON, CB_NOTIFY_OPEN, CB_NOTIFY_TOGGLE_PREFIX
from bot.keyboards.settings import notifications_menu, settings_menu
from bot.services.settings import UnknownCategoryError, muted_categories, set_all, toggle
from bot.texts.settings import NOTIFY_LABELS, NOTIFY_SCREEN, NOTIFY_TOGGLED_OFF, NOTIFY_TOGGLED_ON, SETTINGS_SCREEN
from bot.utils.safe_edit import safe_edit_text

router = Router(name="settings")


@router.callback_query(F.data == CB_MENU_SETTINGS)
async def cb_settings_open(callback: CallbackQuery, state: FSMContext) -> None:
    # Точка возврата «В настройки» — не оставляем висящее ожидание ввода.
    await state.clear()
    await callback.answer()
    await callback.message.answer(SETTINGS_SCREEN, reply_markup=settings_menu())


async def _show_notifications(callback: CallbackQuery, session: AsyncSession) -> None:
    muted = await muted_categories(session, callback.from_user.id)
    await safe_edit_text(callback.message, NOTIFY_SCREEN, reply_markup=notifications_menu(muted))


@router.callback_query(F.data == CB_NOTIFY_OPEN)
async def cb_notify_open(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    await _show_notifications(callback, session)


@router.callback_query(F.data.startswith(CB_NOTIFY_TOGGLE_PREFIX))
async def cb_notify_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    category = callback.data.removeprefix(CB_NOTIFY_TOGGLE_PREFIX)
    try:
        enabled = await toggle(session, callback.from_user.id, category)
    except UnknownCategoryError:
        await callback.answer()
        return
    # Popup — без HTML. Переключение идемпотентно по смыслу: экран всегда показывает факт из БД.
    await callback.answer((NOTIFY_TOGGLED_ON if enabled else NOTIFY_TOGGLED_OFF).format(label=NOTIFY_LABELS[category]))
    await _show_notifications(callback, session)


@router.callback_query(F.data.in_({CB_NOTIFY_ALL_ON, CB_NOTIFY_ALL_OFF}))
async def cb_notify_all(callback: CallbackQuery, session: AsyncSession) -> None:
    await set_all(session, callback.from_user.id, callback.data == CB_NOTIFY_ALL_ON)
    await callback.answer()
    await _show_notifications(callback, session)
