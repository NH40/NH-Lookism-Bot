"""Магазин (клавиатуры)."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constant.mastery import CB_MASTERY_OPEN
from bot.constant.profile import CB_PROFILE_OPEN
from bot.constant.shop import CB_SHOP_BUY_MASTERY_POINT
from bot.constant.genius import CB_GENIUS_ROLL
from bot.constant.contract import CB_CONTRACT_OPEN
from bot.constant.potion import CB_POTION_OPEN
from bot.constant.storage import CB_STORAGE_OPEN
from bot.constant.deposit import CB_DEPOSIT_OPEN
from bot.constant.casino import CB_CASINO_OPEN
from bot.constant.exchange import CB_EXCHANGE_OPEN
from bot.texts.contract import BTN_CONTRACTS
from bot.texts.potion import BTN_POTIONS
from bot.texts.storage import BTN_STORAGE
from bot.texts.deposit import BTN_DEPOSITS
from bot.texts.casino import BTN_CASINO
from bot.texts.exchange import BTN_EXCHANGE
from bot.texts.common import BTN_BACK_TO_PROFILE
from bot.texts.genius import BTN_ROLL as BTN_ROLL_GENIUS
from bot.texts.shop import BTN_BUY_POINT, BTN_TO_MASTERY
from bot.utils.formatting import format_number


def shop_menu(
    *, buy_price: int | None, has_free_points: bool, extra_rows: list | None = None
) -> InlineKeyboardMarkup:
    rows = []
    if buy_price is not None:
        rows.append([InlineKeyboardButton(text=BTN_BUY_POINT.format(price=format_number(buy_price)), callback_data=CB_SHOP_BUY_MASTERY_POINT)])
    if has_free_points:
        rows.append([InlineKeyboardButton(text=BTN_TO_MASTERY, callback_data=CB_MASTERY_OPEN)])
    rows.append([
        InlineKeyboardButton(text=BTN_CONTRACTS, callback_data=CB_CONTRACT_OPEN),
        InlineKeyboardButton(text=BTN_POTIONS, callback_data=CB_POTION_OPEN),
    ])
    rows.append([
        InlineKeyboardButton(text=BTN_STORAGE, callback_data=CB_STORAGE_OPEN),
        InlineKeyboardButton(text=BTN_DEPOSITS, callback_data=CB_DEPOSIT_OPEN),
    ])
    rows.append([
        InlineKeyboardButton(text=BTN_EXCHANGE, callback_data=CB_EXCHANGE_OPEN),
        InlineKeyboardButton(text=BTN_CASINO, callback_data=CB_CASINO_OPEN),
    ])
    rows.extend(extra_rows or [])  # «📚 Обучение» — учителя статистов (`keyboards/school.shop_rows`)
    rows.append([InlineKeyboardButton(text=BTN_ROLL_GENIUS, callback_data=CB_GENIUS_ROLL)])
    rows.append([InlineKeyboardButton(text=BTN_BACK_TO_PROFILE, callback_data=CB_PROFILE_OPEN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
