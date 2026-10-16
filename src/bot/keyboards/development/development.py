"""Экран «📈 Развитие» (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.genius import CB_GENIUS_OPEN
from bot.constant.profile import CB_PROFILE_OPEN
from bot.texts.common import BTN_BACK_TO_PROFILE
from bot.texts.genius import BTN_GENIUS
from bot.constant.unique_technique import CB_TECH_OPEN
from bot.constant.unique_path import CB_PATH_OPEN
from bot.constant.bloodline import CB_BLOODLINE_SCREEN
from bot.constant.awakening import CB_AWAKEN_OPEN
from bot.texts.awakening import BTN_AWAKENING
from bot.texts.bloodline import BTN_BLOODLINE_SCREEN
from bot.texts.unique_path import BTN_PATH
from bot.texts.unique_technique import BTN_TECHNIQUES


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def awakening_button() -> InlineKeyboardButton:
    return _btn(BTN_AWAKENING, CB_AWAKEN_OPEN)


def bloodline_button() -> InlineKeyboardButton:
    return _btn(BTN_BLOODLINE_SCREEN, CB_BLOODLINE_SCREEN)


def path_button() -> InlineKeyboardButton:
    return _btn(BTN_PATH, CB_PATH_OPEN)


def technique_button() -> InlineKeyboardButton:
    return _btn(BTN_TECHNIQUES, CB_TECH_OPEN)


def development_menu(extra_rows: list[list[InlineKeyboardButton]] | None = None) -> InlineKeyboardMarkup:
    """`extra_rows` — кнопки систем, которые добавляются по мере реализации (техники, путь,
    родословная)."""
    rows = [[_btn(BTN_GENIUS, CB_GENIUS_OPEN)]]
    rows.extend(extra_rows or [])
    rows.append([_btn(BTN_BACK_TO_PROFILE, CB_PROFILE_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
