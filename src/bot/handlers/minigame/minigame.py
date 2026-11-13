"""Мини-игры: из бота — сообщение и кнопка прямо на игру в Mini App (играть можно только там)."""
from __future__ import annotations

from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from bot.config.settings import get_settings
from bot.texts.minigame import BTN_PLAY, NO_PRIVATE
from bot.utils.mini_app import play_url, resolve_mini_app_base_url


async def send_play(callback: CallbackQuery, ctx: str, text: str) -> None:
    base = resolve_mini_app_base_url(get_settings().mini_app_url, callback.message.chat.type)
    if not base:
        await callback.answer(NO_PRIVATE, show_alert=True)
        return
    await callback.answer()
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=BTN_PLAY, web_app=WebAppInfo(url=play_url(base, ctx)))]])
    await callback.message.answer(text, reply_markup=markup)
