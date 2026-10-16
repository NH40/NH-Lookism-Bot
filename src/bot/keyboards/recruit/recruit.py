"""Вербовка — статисты (по влиянию, КД 20 минут) и уникальные персонажи (за тикеты) (клавиатуры)."""
from __future__ import annotations

from bot.constant.profile import CB_PROFILE_OPEN
from bot.texts.common import BTN_BACK_TO_PROFILE

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.gacha import CB_GACHA_ROLL
from bot.constant.recruit import CB_RECRUIT_EXTRA
from bot.texts.gacha import BTN_ROLL

BTN_RECRUIT_EXTRA = "🎯 Завербовать статиста"


def recruit_menu(*, tickets: int, cap: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_RECRUIT_EXTRA, callback_data=CB_RECRUIT_EXTRA)],
            [InlineKeyboardButton(text=BTN_ROLL.format(count=tickets, cap=cap), callback_data=CB_GACHA_ROLL)],
            [InlineKeyboardButton(text=BTN_BACK_TO_PROFILE, callback_data=CB_PROFILE_OPEN)],
        ]
    )
