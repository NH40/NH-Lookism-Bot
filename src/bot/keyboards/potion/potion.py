"""Зелья (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.common import CB_MENU_SHOP
from bot.constant.potion import CB_POTION_AUTO_PREFIX, CB_POTION_BUY_PREFIX, CB_POTION_KIND_PREFIX, CB_POTION_OPEN, POTIONS
from bot.texts.common import BTN_BACK
from bot.texts.potion import BTN_AUTO, BTN_AUTO_OFF, BTN_DRINK, BTN_KIND, BTN_KIND_ACTIVE, POTION_NAMES, ROMAN
from bot.utils.formatting import format_countdown, format_number


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def potions_menu(states: dict) -> InlineKeyboardMarkup:
    """Виды зелий по два в ряд; у действующего — тир и остаток."""
    buttons = []
    for kind in POTIONS:
        state = states.get(kind)
        label = (
            BTN_KIND_ACTIVE.format(name=POTION_NAMES[kind], roman=ROMAN[state.tier], countdown=format_countdown(state.left_seconds))
            if state and state.tier
            else BTN_KIND.format(name=POTION_NAMES[kind])
        )
        buttons.append(_btn(label, f"{CB_POTION_KIND_PREFIX}{kind}"))
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([_btn(BTN_BACK, CB_MENU_SHOP)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kind_menu(kind: str, offers: list, auto_slots: int, auto_tier: int) -> InlineKeyboardMarkup:
    unlocked = [o for o in offers if o.unlocked]
    drink = [_btn(BTN_DRINK.format(roman=ROMAN[o.tier], price=format_number(o.price)), f"{CB_POTION_BUY_PREFIX}{kind}:{o.tier}") for o in unlocked]
    rows = [drink[i:i + 2] for i in range(0, len(drink), 2)]
    if auto_slots > 0:
        auto = [
            _btn(BTN_AUTO.format(roman=ROMAN[o.tier]), f"{CB_POTION_AUTO_PREFIX}{kind}:{o.tier}")
            for o in unlocked
            if o.tier != auto_tier
        ]
        rows.extend(auto[i:i + 4] for i in range(0, len(auto), 4))
        if auto_tier:
            rows.append([_btn(BTN_AUTO_OFF, f"{CB_POTION_AUTO_PREFIX}{kind}:0")])
    rows.append([_btn(BTN_BACK, CB_POTION_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
