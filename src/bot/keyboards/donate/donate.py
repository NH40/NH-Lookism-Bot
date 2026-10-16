"""Донат и чёрный рынок (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config.donate import DONATE_PRESETS_RUB
from bot.constant.battle_pass import CB_BP_OPEN
from bot.constant.donate import (
    CB_DONATE_CUSTOM,
    CB_DONATE_OPEN,
    CB_DONATE_PRESET_PREFIX,
    CB_MARKET_BODY,
    CB_MARKET_BODY_BUY,
    CB_MARKET_ITEM_PREFIX,
    CB_MARKET_KIND_PREFIX,
    CB_MARKET_LEVEL_PREFIX,
    CB_MARKET_OPEN,
    CB_MARKET_UNLOCK_PREFIX,
    DONATE_KINDS,
)
from bot.constant.profile import CB_PROFILE_OPEN
from bot.texts.common import BTN_BACK, BTN_BACK_TO_PROFILE
from bot.texts.donate import (
    BTN_BODY,
    BTN_BODY_BUY,
    BTN_CUSTOM,
    BTN_ITEM_LOCKED,
    BTN_ITEM_OPEN,
    BTN_KIND,
    BTN_LEVEL,
    BTN_MARKET,
    BTN_PASS,
    BTN_PRESET,
    BTN_TO_DONATE,
    BTN_UNLOCK,
)
from bot.utils.formatting import format_number


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def donate_menu() -> InlineKeyboardMarkup:
    presets = [_btn(BTN_PRESET.format(amount=format_number(a)), f"{CB_DONATE_PRESET_PREFIX}{a}") for a in DONATE_PRESETS_RUB]
    rows = [presets[i:i + 3] for i in range(0, len(presets), 3)]
    rows.append([_btn(BTN_CUSTOM, CB_DONATE_CUSTOM)])
    rows.append([_btn(BTN_MARKET, CB_MARKET_OPEN)])
    rows.append([_btn(BTN_BACK_TO_PROFILE, CB_PROFILE_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_donate() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(BTN_BACK, CB_DONATE_OPEN)]])


def market_menu() -> InlineKeyboardMarkup:
    rows = [[_btn(BTN_BODY, CB_MARKET_BODY)]]
    rows.append([_btn(BTN_KIND[k], f"{CB_MARKET_KIND_PREFIX}{k}") for k in DONATE_KINDS])
    rows.append([_btn(BTN_PASS, CB_BP_OPEN)])
    rows.append([_btn(BTN_TO_DONATE, CB_DONATE_OPEN)])
    rows.append([_btn(BTN_BACK_TO_PROFILE, CB_PROFILE_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def body_menu(price: int | None) -> InlineKeyboardMarkup:
    rows = [[_btn(BTN_BODY_BUY.format(price=format_number(price)), CB_MARKET_BODY_BUY)]] if price else []
    rows.append([_btn(BTN_BACK, CB_MARKET_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kind_menu(kind: str, items: list, names: dict[str, str]) -> InlineKeyboardMarkup:
    buttons = [
        _btn(
            BTN_ITEM_OPEN.format(name=names.get(i.code, i.code), level=i.level)
            if i.level
            else BTN_ITEM_LOCKED.format(name=names.get(i.code, i.code), price=format_number(i.next_price)),
            f"{CB_MARKET_ITEM_PREFIX}{kind}:{i.code}",
        )
        for i in items
    ]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([_btn(BTN_BACK, CB_MARKET_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def item_menu(item) -> InlineKeyboardMarkup:
    rows = []
    if item.next_price is not None:
        if item.level == 0:
            rows.append([_btn(BTN_UNLOCK.format(price=format_number(item.next_price)), f"{CB_MARKET_UNLOCK_PREFIX}{item.kind}:{item.code}")])
        else:
            rows.append([
                _btn(BTN_LEVEL.format(level=item.level + 1, price=format_number(item.next_price)),
                     f"{CB_MARKET_LEVEL_PREFIX}{item.kind}:{item.code}")
            ])
    rows.append([_btn(BTN_BACK, f"{CB_MARKET_KIND_PREFIX}{item.kind}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
