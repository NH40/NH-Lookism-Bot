"""Админка/промокоды: клавиатуры."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.admin import CB_ADMIN_OPEN, CB_ADMIN_SECTION_PREFIX, SECTION_PROMO
from bot.constant.admin.promo_admin import (
    CB_PROMO_DELETE_ASK_PREFIX,
    CB_PROMO_DELETE_PREFIX,
    CB_PROMO_NEW,
    CB_PROMO_TOGGLE_PREFIX,
    CB_PROMO_VIEW_PREFIX,
)
from bot.texts.admin.promo_admin import (
    BTN_ACTIVATE,
    BTN_BACK,
    BTN_BACK_LIST,
    BTN_CONFIRM_DELETE,
    BTN_DEACTIVATE,
    BTN_DELETE,
    BTN_NEW,
)

_LIST_CB = f"{CB_ADMIN_SECTION_PREFIX}{SECTION_PROMO}"


def _btn(text: str, cb: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=cb)


def list_menu(items: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    """items: (id, подпись кнопки)."""
    rows = [[_btn(label, f"{CB_PROMO_VIEW_PREFIX}{pid}")] for pid, label in items]
    rows.append([_btn(BTN_NEW, CB_PROMO_NEW)])
    rows.append([_btn(BTN_BACK, CB_ADMIN_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def detail_menu(promo_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle = _btn(BTN_DEACTIVATE if is_active else BTN_ACTIVATE, f"{CB_PROMO_TOGGLE_PREFIX}{promo_id}")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [toggle, _btn(BTN_DELETE, f"{CB_PROMO_DELETE_ASK_PREFIX}{promo_id}")],
            [_btn(BTN_BACK_LIST, _LIST_CB)],
        ]
    )


def delete_confirm_menu(promo_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(BTN_CONFIRM_DELETE, f"{CB_PROMO_DELETE_PREFIX}{promo_id}")],
            [_btn(BTN_BACK, f"{CB_PROMO_VIEW_PREFIX}{promo_id}")],
        ]
    )


def back_to_list() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(BTN_BACK_LIST, _LIST_CB)]])
