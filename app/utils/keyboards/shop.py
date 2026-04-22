from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def shop_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🧪 Зелья",     callback_data="shop_potions"),
        InlineKeyboardButton(text="👥 Статисты",  callback_data="shop_recruits"),
    )
    builder.row(
        InlineKeyboardButton(text="🔷 Очки пути", callback_data="shop_points"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
    return builder.as_markup()