"""Гайд `/help` (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.help import CB_HELP_OPEN, CB_HELP_SECTION_PREFIX
from bot.texts.help import BTN_BACK_TO_MENU, BTN_NEXT, BTN_PREV, HELP_SECTIONS


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def help_menu() -> InlineKeyboardMarkup:
    """Все разделы по два в ряд."""
    buttons = [_btn(label, f"{CB_HELP_SECTION_PREFIX}{code}") for code, label, _ in HELP_SECTIONS]
    return InlineKeyboardMarkup(inline_keyboard=[buttons[i : i + 2] for i in range(0, len(buttons), 2)])


def section_menu(code: str) -> InlineKeyboardMarkup:
    """Раздел: соседние разделы стрелками (читать подряд) и возврат к списку."""
    codes = [c for c, _, _ in HELP_SECTIONS]
    i = codes.index(code)
    nav = []
    if i > 0:
        nav.append(_btn(f"{BTN_PREV} {HELP_SECTIONS[i - 1][1]}", f"{CB_HELP_SECTION_PREFIX}{codes[i - 1]}"))
    if i < len(codes) - 1:
        nav.append(_btn(f"{HELP_SECTIONS[i + 1][1]} {BTN_NEXT}", f"{CB_HELP_SECTION_PREFIX}{codes[i + 1]}"))
    return InlineKeyboardMarkup(inline_keyboard=[nav, [_btn(BTN_BACK_TO_MENU, CB_HELP_OPEN)]])
