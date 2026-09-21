"""Тренировки — личная (характеристики, КД 10 минут) и тренировка статистов (3 этапа: прокачка мощи / пробуждение звёзд / повышение ранга) (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.training import CB_TRAIN_EXTRAS_RUN

BTN_TRAIN_EXTRAS_RUN = "🏋️ Тренировать статистов"


def train_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=BTN_TRAIN_EXTRAS_RUN, callback_data=CB_TRAIN_EXTRAS_RUN)]]
    )
