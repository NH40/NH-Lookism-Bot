"""Админка — Настройки на лету (клавиатуры)."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.admin import CB_ADMIN_OPEN
from bot.constant.admin.live_config import (
    CB_CONFIG_DUR_PREFIX,
    CB_CONFIG_KEY_PREFIX,
    CB_CONFIG_LIST,
    CB_CONFIG_RESET_PREFIX,
    CB_CONFIG_SET_PREFIX,
    CONFIG_DURATIONS,
)
from bot.texts.admin import BTN_BACK
from bot.texts.admin.live_config import BTN_CHANGE, BTN_RESET


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def list_menu(rows: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """rows: [(key, подпись)]"""
    keyboard = [[_btn(label, f"{CB_CONFIG_KEY_PREFIX}{key}")] for key, label in rows]
    keyboard.append([_btn(BTN_BACK, CB_ADMIN_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def key_menu(key: str, overridden: bool) -> InlineKeyboardMarkup:
    rows = [[_btn(BTN_CHANGE, f"{CB_CONFIG_SET_PREFIX}{key}")]]
    if overridden:
        rows.append([_btn(BTN_RESET, f"{CB_CONFIG_RESET_PREFIX}{key}")])
    rows.append([_btn(BTN_BACK, CB_CONFIG_LIST)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def duration_menu(key: str) -> InlineKeyboardMarkup:
    row = [_btn(label, f"{CB_CONFIG_DUR_PREFIX}{key}:{hours}") for hours, label in CONFIG_DURATIONS]
    return InlineKeyboardMarkup(inline_keyboard=[row[:3], row[3:], [_btn(BTN_BACK, f"{CB_CONFIG_KEY_PREFIX}{key}")]])


def back_to_key(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn(BTN_BACK, f"{CB_CONFIG_KEY_PREFIX}{key}")]])
