"""Ячейки хранения (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.common import CB_MENU_SHOP
from bot.constant.resource import RESOURCES
from bot.constant.storage import (
    CB_STORAGE_CELL_PREFIX,
    CB_STORAGE_OPEN,
    CB_STORAGE_PUT_RES_PREFIX,
    CB_STORAGE_PUT_SQUAD_PREFIX,
    CB_STORAGE_PUT_STATISTS_PREFIX,
    CB_STORAGE_TAKE_ALL_PREFIX,
    CB_STORAGE_TAKE_PART_PREFIX,
    CB_STORAGE_TOPUP_PREFIX,
    CB_STORAGE_UNLOCK_PREFIX,
)
from bot.texts.common import BTN_BACK
from bot.texts.resource import resource_label
from bot.texts.storage import (
    BTN_CELL,
    BTN_CELL_EMPTY,
    BTN_PUT_STATISTS,
    BTN_SQUAD,
    BTN_TAKE_ALL,
    BTN_TAKE_PART,
    BTN_TOPUP,
    BTN_UNLOCK,
)
from bot.utils.formatting import format_number


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def storage_menu(views: list, item_label) -> InlineKeyboardMarkup:
    rows = []
    next_locked = True
    for v in views:
        if v.opened:
            label = BTN_CELL_EMPTY.format(n=v.slot) if v.empty else BTN_CELL.format(n=v.slot, item=item_label(v))
            rows.append([_btn(label, f"{CB_STORAGE_CELL_PREFIX}{v.slot}")])
        elif next_locked:
            rows.append([_btn(BTN_UNLOCK.format(n=v.slot, cost=format_number(v.open_cost)), f"{CB_STORAGE_UNLOCK_PREFIX}{v.slot}")])
            next_locked = False
    rows.append([_btn(BTN_BACK, CB_MENU_SHOP)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def empty_cell_menu(slot: int) -> InlineKeyboardMarkup:
    buttons = [_btn(resource_label(code), f"{CB_STORAGE_PUT_RES_PREFIX}{slot}:{code}") for code in RESOURCES]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([_btn(BTN_PUT_STATISTS, f"{CB_STORAGE_PUT_STATISTS_PREFIX}{slot}")])
    rows.append([_btn(BTN_BACK, CB_STORAGE_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def filled_cell_menu(slot: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(BTN_TAKE_ALL, f"{CB_STORAGE_TAKE_ALL_PREFIX}{slot}"), _btn(BTN_TAKE_PART, f"{CB_STORAGE_TAKE_PART_PREFIX}{slot}")],
            [_btn(BTN_TOPUP, f"{CB_STORAGE_TOPUP_PREFIX}{slot}")],
            [_btn(BTN_BACK, CB_STORAGE_OPEN)],
        ]
    )


def squads_menu(slot: int, squads: list[tuple[str, str, int]]) -> InlineKeyboardMarkup:
    """(ключ отряда, подпись, сколько бойцов)."""
    rows = [
        [_btn(BTN_SQUAD.format(title=title, total=format_number(total)), f"{CB_STORAGE_PUT_SQUAD_PREFIX}{slot}:{key}")]
        for key, title, total in squads
    ]
    rows.append([_btn(BTN_BACK, f"{CB_STORAGE_CELL_PREFIX}{slot}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_cell(slot: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(BTN_BACK, f"{CB_STORAGE_CELL_PREFIX}{slot}")]])
