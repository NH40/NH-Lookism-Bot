"""Родословная (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.bloodline import (
    BLOODLINES,
    CB_BLOODLINE2_CHOOSE_PREFIX,
    CB_BLOODLINE2_LEVEL_UP,
    CB_BLOODLINE2_LIST,
    CB_BLOODLINE2_SCREEN,
    CB_BLOODLINE_LEVEL_UP,
    CB_BLOODLINE_LIST,
    CB_BLOODLINE_PICK_PREFIX,
    CB_BLOODLINE_VIEW_PREFIX,
)
from bot.constant.bloodline import CB_BLOODLINE_SCREEN
from bot.constant.common import CB_MENU_DEVELOPMENT
from bot.texts.development import BTN_BACK_TO_DEVELOPMENT
from bot.texts.bloodline import (
    BLOODLINE_NAMES,
    BTN_BACK_TO_BLOODLINE,
    BTN_BACK_TO_LIST,
    BTN_BLOODLINE,
    BTN_BLOODLINE2_CHOOSE,
    BTN_BLOODLINE2_LEVEL_UP,
    BTN_LEVEL_UP,
    BTN_PICK,
)


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def choose_menu() -> InlineKeyboardMarkup:
    buttons = [_btn(BTN_BLOODLINE.format(name=BLOODLINE_NAMES[c]), f"{CB_BLOODLINE_VIEW_PREFIX}{c}") for c in BLOODLINES]
    return InlineKeyboardMarkup(inline_keyboard=[buttons[i:i + 2] for i in range(0, len(buttons), 2)])


def detail_menu(
    cost: int | None, *, choose2: bool = False, second_label: str | None = None
) -> InlineKeyboardMarkup:
    """`second_label` — подпись кнопки экрана второй родословной (второе тело): её уровни
    видны там всегда, и на максимуме тоже (тестеры 2026-10-15: «вижу только основу»)."""
    rows = []
    if cost is not None:
        rows.append([_btn(BTN_LEVEL_UP.format(cost=cost), CB_BLOODLINE_LEVEL_UP)])
    if choose2:
        rows.append([_btn(BTN_BLOODLINE2_CHOOSE, CB_BLOODLINE2_LIST)])
    if second_label:
        rows.append([_btn(second_label, CB_BLOODLINE2_SCREEN)])
    rows.append([_btn(BTN_BACK_TO_DEVELOPMENT, CB_MENU_DEVELOPMENT)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def detail2_menu(cost2: int | None) -> InlineKeyboardMarkup:
    """Экран второй родословной: прокачка (если не максимум) и назад к первой."""
    rows = []
    if cost2 is not None:
        rows.append([_btn(BTN_BLOODLINE2_LEVEL_UP.format(cost=cost2), CB_BLOODLINE2_LEVEL_UP)])
    rows.append([_btn(BTN_BACK_TO_BLOODLINE, CB_BLOODLINE_SCREEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def view_menu(code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(BTN_PICK, f"{CB_BLOODLINE_PICK_PREFIX}{code}")],
            [_btn(BTN_BACK_TO_LIST, CB_BLOODLINE_LIST)],
        ]
    )


def choose2_menu(first: str | None) -> InlineKeyboardMarkup:
    buttons = [
        _btn(BTN_BLOODLINE.format(name=BLOODLINE_NAMES[c]), f"{CB_BLOODLINE2_CHOOSE_PREFIX}{c}")
        for c in BLOODLINES
        if c != first
    ]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([_btn(BTN_BACK_TO_BLOODLINE, CB_BLOODLINE_SCREEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
