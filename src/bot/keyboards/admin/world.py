"""Админка «Районы, города, императоры»: клавиатуры."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.admin import CB_ADMIN_OPEN
from bot.constant.admin.world import (
    CB_W_CH_ASK_PREFIX, CB_W_CITY_PREFIX, CB_W_DEL_EMP_ASK_PREFIX, CB_W_DISTRICT_PREFIX, CB_W_FIND,
    CB_W_RESET_ASK_PREFIX, CB_W_SET_EMP_PREFIX, CB_W_SET_OWNER_PREFIX, CB_W_WAR_ASK_PREFIX,
)
from bot.texts.admin.world import (
    BTN_BACK, BTN_CANCEL_CH, BTN_CANCEL_WAR, BTN_DEL_EMP, BTN_FIND_CITY, BTN_NO, BTN_RESET, BTN_SET_EMP,
    BTN_SET_OWNER, BTN_TO_CITY, BTN_YES,
)


def _b(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _m(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def menu() -> InlineKeyboardMarkup:
    return _m([[_b(BTN_FIND_CITY, CB_W_FIND)], [_b(BTN_BACK, CB_ADMIN_OPEN)]])


def back_to_menu_only() -> InlineKeyboardMarkup:
    from bot.constant.admin import CB_ADMIN_SECTION_PREFIX, SECTION_WORLD

    return _m([[_b(BTN_BACK, f"{CB_ADMIN_SECTION_PREFIX}{SECTION_WORLD}")]])


def pick_cities(cities: list[tuple[int, str, str]]) -> InlineKeyboardMarkup:
    rows = [[_b(f"{name} ({country})", f"{CB_W_CITY_PREFIX}{cid}")] for cid, name, country in cities]
    return _m(rows + back_to_menu_only().inline_keyboard)


def city_card(city_id: int, numbers: list[tuple[int, int]], has_emperor: bool) -> InlineKeyboardMarkup:
    """numbers: (district_id, number)."""
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for did, number in numbers:
        row.append(_b(str(number), f"{CB_W_DISTRICT_PREFIX}{did}"))
        if len(row) == 8:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([_b(BTN_SET_EMP, f"{CB_W_SET_EMP_PREFIX}{city_id}")])
    if has_emperor:
        rows.append([_b(BTN_DEL_EMP, f"{CB_W_DEL_EMP_ASK_PREFIX}{city_id}")])
        rows.append([_b(BTN_CANCEL_WAR, f"{CB_W_WAR_ASK_PREFIX}{city_id}")])
    rows.append([_b(BTN_CANCEL_CH, f"{CB_W_CH_ASK_PREFIX}{city_id}")])
    return _m(rows + back_to_menu_only().inline_keyboard)


def district_card(district_id: int, city_id: int) -> InlineKeyboardMarkup:
    return _m([
        [_b(BTN_SET_OWNER, f"{CB_W_SET_OWNER_PREFIX}{district_id}")],
        [_b(BTN_RESET, f"{CB_W_RESET_ASK_PREFIX}{district_id}")],
        [_b(BTN_TO_CITY, f"{CB_W_CITY_PREFIX}{city_id}")],
    ])


def confirm(ok_data: str, back_data: str) -> InlineKeyboardMarkup:
    return _m([[_b(BTN_YES, ok_data)], [_b(BTN_NO, back_data)]])


def to_city(city_id: int) -> InlineKeyboardMarkup:
    return _m([[_b(BTN_TO_CITY, f"{CB_W_CITY_PREFIX}{city_id}")]])
