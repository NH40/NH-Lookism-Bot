"""Пути (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.common import CB_MENU_DEVELOPMENT
from bot.constant.unique_path import (
    CB_PATH_ACTIVATE2_PREFIX,
    CB_PATH_ACTIVATE_PREFIX,
    CB_PATH_AWAKEN_PREFIX,
    CB_PATH_CLAIM_CONVICTION,
    CB_PATH_CLAIM_PATH,
    CB_PATH_LEVEL_UP,
    CB_PATH_LEVEL_UP2,
    CB_PATH_OPEN,
    PATH_AWAKEN_RANDOM,
)
from bot.texts.development import BTN_BACK_TO_DEVELOPMENT
from bot.texts.unique_path import (
    BTN_ACTIVATE,
    BTN_ACTIVATE2,
    BTN_AWAKEN,
    BTN_AWAKEN_BOUGHT,
    BTN_AWAKEN_RANDOM,
    BTN_BACK_TO_PATH,
    BTN_CLAIM_CONVICTION,
    BTN_LEVEL_UP,
    BTN_LEVEL_UP2,
    PATH_NAMES,
)
from bot.utils.formatting import format_number


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def path_menu(
    *, claim_conviction: bool = False, awaken_cost: int | None = None, cost: int | None = None, others: list[str] | None = None,
    cost2: int | None = None, others2: list[str] | None = None,
) -> InlineKeyboardMarkup:
    rows = []
    if claim_conviction:
        rows.append([_btn(BTN_CLAIM_CONVICTION, CB_PATH_CLAIM_CONVICTION)])
    if awaken_cost is not None:
        rows.append([_btn(BTN_AWAKEN.format(cost=format_number(awaken_cost)), CB_PATH_CLAIM_PATH)])
    if cost is not None:
        rows.append([_btn(BTN_LEVEL_UP.format(cost=format_number(cost)), CB_PATH_LEVEL_UP)])
    if cost2 is not None:
        rows.append([_btn(BTN_LEVEL_UP2.format(cost=format_number(cost2)), CB_PATH_LEVEL_UP2)])
    rows.extend([_btn(BTN_ACTIVATE2.format(name=PATH_NAMES[c]), f"{CB_PATH_ACTIVATE2_PREFIX}{c}")] for c in (others2 or []))
    rows.extend([_btn(BTN_ACTIVATE.format(name=PATH_NAMES[c]), f"{CB_PATH_ACTIVATE_PREFIX}{c}")] for c in (others or []))
    rows.append([_btn(BTN_BACK_TO_DEVELOPMENT, CB_MENU_DEVELOPMENT)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def awaken_choice_menu(bought: tuple[str, ...]) -> InlineKeyboardMarkup:
    rows = [[_btn(BTN_AWAKEN_RANDOM, f"{CB_PATH_AWAKEN_PREFIX}{PATH_AWAKEN_RANDOM}")]]
    rows.extend([_btn(BTN_AWAKEN_BOUGHT.format(name=PATH_NAMES[c]), f"{CB_PATH_AWAKEN_PREFIX}{c}")] for c in bought)
    rows.append([_btn(BTN_BACK_TO_PATH, CB_PATH_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
