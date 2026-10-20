"""Крутки за тикеты — экран результата (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.gacha import CB_GACHA_ROLL, CB_GACHA_ROLL_MANY
from bot.constant.recruit import CB_RECRUIT_OPEN
from bot.texts.common import BTN_BACK
from bot.texts.gacha import BTN_ROLL_AGAIN, BTN_ROLL_MANY


def roll_result_menu() -> InlineKeyboardMarkup:
    # «Крутить ещё» — тот же callback, что и первая крутка: кнопка всегда в одном месте
    # под последним результатом (тот же приём, что в UAP). «Назад» — в вербовку, откуда
    # крутили (тестер 2026-10-14: коллекция сразу после крутки не нужна).
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_ROLL_AGAIN, callback_data=CB_GACHA_ROLL)],
            [InlineKeyboardButton(text=BTN_ROLL_MANY, callback_data=CB_GACHA_ROLL_MANY)],
            [InlineKeyboardButton(text=BTN_BACK, callback_data=CB_RECRUIT_OPEN)],
        ]
    )
