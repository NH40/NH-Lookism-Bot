"""Общее reply-меню бота (хендлеры)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.constant.common import CB_NOOP
from bot.texts.common import SECTION_IN_DEVELOPMENT

router = Router(name="common")

_PLACEHOLDER_MENU_CALLBACKS: tuple[str, ...] = ()


@router.callback_query(F.data == CB_NOOP)
async def cb_noop(callback: CallbackQuery) -> None:
    """Кнопка-индикатор (номер страницы и т.п.) — ничего не делает, просто гасит
    "часики" в клиенте Telegram."""
    await callback.answer()


@router.callback_query(F.data.in_(_PLACEHOLDER_MENU_CALLBACKS))
async def cb_menu_placeholder(callback: CallbackQuery) -> None:
    """Разделы главного меню без реализованного домена (Развитие/Магазин/Кланы/
    Задания/Настройки) — честный popup-алерт (без HTML, см. CLAUDE.md UAP про
    popup+HTML), тот же принцип, что `PlaceholderPage` в Mini App: не выдумываем
    контент несуществующих экранов."""
    await callback.answer(SECTION_IN_DEVELOPMENT, show_alert=True)
