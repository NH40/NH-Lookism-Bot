"""Админка/рассылка и массовая выдача: клавиатуры."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.admin import CB_ADMIN_OPEN, CB_ADMIN_SECTION_PREFIX, SECTION_MASS
from bot.constant.admin.mass import (
    CB_MASS_BROADCAST,
    CB_MASS_BROADCAST_GO,
    CB_MASS_FILTER_PREFIX,
    CB_MASS_GRANT,
    CB_MASS_GRANT_GO,
    CB_MASS_RES_PREFIX,
    CB_MASS_SKIP_BUTTON,
    FILTERS,
)
from bot.constant.resource import RESOURCES
from bot.texts.admin.mass import BTN_APPLY, BTN_BACK, BTN_BROADCAST, BTN_GRANT, BTN_SEND, BTN_SKIP, FILTER_LABELS
from bot.texts.resource import resource_label

_ROOT_CB = f"{CB_ADMIN_SECTION_PREFIX}{SECTION_MASS}"


def _btn(text: str, cb: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=cb)


def menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn(BTN_BROADCAST, CB_MASS_BROADCAST)],
            [_btn(BTN_GRANT, CB_MASS_GRANT)],
            [_btn(BTN_BACK, CB_ADMIN_OPEN)],
        ]
    )


def back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(BTN_BACK, _ROOT_CB)]])


def filter_menu() -> InlineKeyboardMarkup:
    rows = [[_btn(FILTER_LABELS[code], f"{CB_MASS_FILTER_PREFIX}{code}")] for code in FILTERS]
    rows.append([_btn(BTN_BACK, _ROOT_CB)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def resource_menu() -> InlineKeyboardMarkup:
    buttons = [_btn(resource_label(code), f"{CB_MASS_RES_PREFIX}{code}") for code in RESOURCES]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append([_btn(BTN_BACK, _ROOT_CB)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def skip_button_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(BTN_SKIP, CB_MASS_SKIP_BUTTON)], [_btn(BTN_BACK, _ROOT_CB)]])


def broadcast_confirm_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(BTN_SEND, CB_MASS_BROADCAST_GO)], [_btn(BTN_BACK, _ROOT_CB)]])


def grant_confirm_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(BTN_APPLY, CB_MASS_GRANT_GO)], [_btn(BTN_BACK, _ROOT_CB)]])
