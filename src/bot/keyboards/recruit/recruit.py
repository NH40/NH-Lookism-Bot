"""Вербовка — статисты (по влиянию, КД 20 минут) и уникальные персонажи (за тикеты) (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.recruit import CB_RECRUIT_EXTRA

BTN_RECRUIT_EXTRA = "🎯 Завербовать статиста"


def recruit_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=BTN_RECRUIT_EXTRA, callback_data=CB_RECRUIT_EXTRA)]]
    )
