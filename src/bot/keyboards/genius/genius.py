"""Гениальность (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.common import CB_MENU_DEVELOPMENT
from bot.constant.genius import (
    CB_GENIUS_ACTIVATE_PREFIX,
    CB_GENIUS_LEVEL_UP_PREFIX,
    CB_GENIUS_OPEN,
    CB_GENIUS_ROLL,
    CB_GENIUS_VIEW_PREFIX,
)
from bot.texts.development import BTN_BACK_TO_DEVELOPMENT
from bot.texts.genius import (
    BTN_ACTIVATE,
    BTN_BACK_TO_GENIUS,
    BTN_GENIUS_ITEM,
    BTN_LEVEL_UP,
    BTN_ROLL,
    GENIUS_NAMES,
    MARK_ACTIVE,
    MARK_OWNED,
)
from bot.utils.formatting import format_number


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def genius_menu(owned: dict[str, int], active: str | None) -> InlineKeyboardMarkup:
    buttons = [
        _btn(
            BTN_GENIUS_ITEM.format(mark=MARK_ACTIVE if code == active else MARK_OWNED, name=GENIUS_NAMES[code], level=level),
            f"{CB_GENIUS_VIEW_PREFIX}{code}",
        )
        for code, level in owned.items()
    ]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([_btn(BTN_ROLL, CB_GENIUS_ROLL)])
    rows.append([_btn(BTN_BACK_TO_DEVELOPMENT, CB_MENU_DEVELOPMENT)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def genius_detail_menu(code: str, *, cost: int | None, is_active: bool) -> InlineKeyboardMarkup:
    rows = []
    if cost is not None:
        rows.append([_btn(BTN_LEVEL_UP.format(cost=format_number(cost)), f"{CB_GENIUS_LEVEL_UP_PREFIX}{code}")])
    if not is_active:
        rows.append([_btn(BTN_ACTIVATE, f"{CB_GENIUS_ACTIVATE_PREFIX}{code}")])
    rows.append([_btn(BTN_BACK_TO_GENIUS, CB_GENIUS_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
