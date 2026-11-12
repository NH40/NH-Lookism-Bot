"""Экран подтверждения нападения на соклановца (общий для всех PvP-кнопок)."""
from __future__ import annotations

from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.common import CB_NOOP
from bot.services.clan.clanmate import CONFIRM_SUFFIX
from bot.utils.formatting import esc

TEXT = (
    "⚠️ <b>{name} — твой соклановец.</b>\n"
    "Точно напасть? Бой будет настоящим: потери, захват и награды как в обычном бою."
)
BTN_YES = "⚔️ Да, напасть"
BTN_NO = "✖️ Отмена"


async def ask_clanmate(callback: CallbackQuery, name: str, data: str) -> None:
    """Вместо атаки — вопрос. «Да» повторяет ту же кнопку с суффиксом подтверждения."""
    await callback.answer()
    await callback.message.answer(
        TEXT.format(name=esc(name)),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=BTN_YES, callback_data=f"{data}{CONFIRM_SUFFIX}"),
            InlineKeyboardButton(text=BTN_NO, callback_data=CB_NOOP),
        ]]),
    )
