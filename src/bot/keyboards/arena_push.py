"""Кнопки пуша онлайн-боя (2026-11-20): открыть бой в Mini App сразу на экране боя или в боте текстом."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from bot.config.settings import get_settings
from bot.utils.mini_app import mini_app_url

CB_BATTLE_REFRESH = "ar:r:"  # то же, что handlers/arena CB_REFRESH — текстовый экран боя


def battle_markup(battle_id: str) -> InlineKeyboardMarkup:
    rows = []
    base = get_settings().mini_app_url
    if base:
        url = f"{mini_app_url(base)}&battle={battle_id}"
        rows.append([InlineKeyboardButton(text="⚔️ Войти в бой", web_app=WebAppInfo(url=url))])
    rows.append([InlineKeyboardButton(text="💬 Бой в боте (без мини-игр)", callback_data=f"{CB_BATTLE_REFRESH}{battle_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
