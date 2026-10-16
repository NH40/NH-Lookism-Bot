"""Общие клавиатуры."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.texts.common import BTN_BACK


def back_menu(callback_data: str, text: str = BTN_BACK) -> InlineKeyboardMarkup:
    """Одна кнопка «◀️ Назад» под сообщением-результатом — чтобы экран не был тупиком."""
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=callback_data)]])
