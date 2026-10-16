"""Вклады (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config.deposit import DEPOSIT_RATES
from bot.constant.common import CB_MENU_SHOP
from bot.constant.deposit import (
    CB_DEPOSIT_CLAIM_PREFIX,
    CB_DEPOSIT_NEW,
    CB_DEPOSIT_OPEN,
    CB_DEPOSIT_RES_PREFIX,
    CB_DEPOSIT_TERM_PREFIX,
)
from bot.constant.resource import NO_MINT_RESOURCES, RESOURCES
from bot.texts.common import BTN_BACK
from bot.texts.deposit import BTN_CLAIM_EARLY, BTN_CLAIM_READY, BTN_NEW_DEPOSIT, BTN_TERM
from bot.texts.resource import amount_label, resource_label


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def deposits_menu(deposits: list, can_open: bool) -> InlineKeyboardMarkup:
    rows = []
    for d in deposits:
        label = (
            BTN_CLAIM_READY.format(id=d.id, payout=amount_label(d.resource, d.payout))
            if d.ready
            else BTN_CLAIM_EARLY.format(id=d.id)
        )
        rows.append([_btn(label, f"{CB_DEPOSIT_CLAIM_PREFIX}{d.id}")])
    if can_open:
        rows.append([_btn(BTN_NEW_DEPOSIT, CB_DEPOSIT_NEW)])
    rows.append([_btn(BTN_BACK, CB_MENU_SHOP)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def resources_menu() -> InlineKeyboardMarkup:
    buttons = [_btn(resource_label(code), f"{CB_DEPOSIT_RES_PREFIX}{code}") for code in RESOURCES if code not in NO_MINT_RESOURCES]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([_btn(BTN_BACK, CB_DEPOSIT_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def terms_menu(resource: str, rates: dict[int, float]) -> InlineKeyboardMarkup:
    buttons = [
        _btn(BTN_TERM.format(hours=hours, percent=f"{rates[hours] * 100:g}"), f"{CB_DEPOSIT_TERM_PREFIX}{resource}:{hours}")
        for hours in DEPOSIT_RATES
    ]
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    rows.append([_btn(BTN_BACK, CB_DEPOSIT_NEW)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_deposits() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(BTN_BACK, CB_DEPOSIT_OPEN)]])
