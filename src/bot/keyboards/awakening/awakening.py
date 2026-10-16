"""Пробуждение (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.awakening import CB_AWAKEN_ASK, CB_AWAKEN_CONFIRM, CB_AWAKEN_OPEN
from bot.constant.common import CB_MENU_DEVELOPMENT
from bot.texts.awakening import BTN_AWAKEN, BTN_AWAKEN_CONFIRM
from bot.texts.development import BTN_BACK_TO_DEVELOPMENT


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def awakening_menu(*, ready: bool) -> InlineKeyboardMarkup:
    rows = [[_btn(BTN_AWAKEN, CB_AWAKEN_ASK)]] if ready else []
    rows.append([_btn(BTN_BACK_TO_DEVELOPMENT, CB_MENU_DEVELOPMENT)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn(BTN_AWAKEN_CONFIRM, CB_AWAKEN_CONFIRM)], [_btn(BTN_BACK_TO_DEVELOPMENT, CB_AWAKEN_OPEN)]]
    )
