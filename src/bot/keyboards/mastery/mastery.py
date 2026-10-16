"""Мастерство — экран цепочки, бой с Томом, вложение очков (клавиатуры)."""
from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.common import CB_MENU_SHOP
from bot.constant.mastery import CB_MASTERY_INVEST_PREFIX, CB_MASTERY_OPEN, CB_MASTERY_TOM_FIGHT
from bot.constant.profile import CB_PROFILE_OPEN
from bot.texts.common import BTN_BACK_TO_PROFILE
from bot.texts.mastery import BTN_FIGHT_TOM, BTN_INVEST, BTN_OPEN_MASTERY, BTN_SHOP
from bot.texts.profile import MASTERY_LABELS


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def mastery_menu(*, tom: bool, investable: Sequence[str], shop: bool) -> InlineKeyboardMarkup:
    """`investable` — мастерства, куда можно вложить очко (есть свободные и ниже ступени этапа)."""
    rows = []
    if tom:
        rows.append([_btn(BTN_FIGHT_TOM, CB_MASTERY_TOM_FIGHT)])
    invest = [_btn(BTN_INVEST.format(label=MASTERY_LABELS[m]), f"{CB_MASTERY_INVEST_PREFIX}{m}") for m in investable]
    rows.extend(invest[i : i + 2] for i in range(0, len(invest), 2))
    if shop:
        rows.append([_btn(BTN_SHOP, CB_MENU_SHOP)])
    rows.append([_btn(BTN_BACK_TO_PROFILE, CB_PROFILE_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def open_mastery_menu() -> InlineKeyboardMarkup:
    """Под пушем о новом задании и под итогом боя с Томом."""
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(BTN_OPEN_MASTERY, CB_MASTERY_OPEN)]])
