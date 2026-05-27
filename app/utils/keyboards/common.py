from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_kb(has_vvip: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⚔️ Атака",       callback_data="attack"),
        InlineKeyboardButton(text="👥 Группировка",  callback_data="squad"),
    )
    builder.row(
        InlineKeyboardButton(text="🃏 Колода",       callback_data="deck"),
        InlineKeyboardButton(text="🏆 Титулы",       callback_data="titles"),
    )
    builder.row(
        InlineKeyboardButton(text="🏢 Бизнес",       callback_data="business"),
        InlineKeyboardButton(text="⚡ Навыки",       callback_data="skills"),
    )
    builder.row(
        InlineKeyboardButton(text="🛒 Магазин",      callback_data="shop"),
        InlineKeyboardButton(text="🏛 Аукцион",      callback_data="auction"),
    )
    builder.row(
        InlineKeyboardButton(text="🏋 Тренировка",   callback_data="training_menu"),
        InlineKeyboardButton(text="⚔️ Рейд",         callback_data="raid_menu"),
    )
    builder.row(
        InlineKeyboardButton(text="🏪 Биржа", callback_data="market_menu"),
        InlineKeyboardButton(text="🏯 Кланы", callback_data="clans_menu"),
    )
    builder.row(
        InlineKeyboardButton(text="🗺 Походы",  callback_data="campaigns_menu"),
        InlineKeyboardButton(text="⚔️ Боссы",   callback_data="bosses_menu"),
    )
    builder.row(
        InlineKeyboardButton(text="🏦 Банк",    callback_data="bank_menu"),
        InlineKeyboardButton(text="📋 Задания", callback_data="daily_quests"),
    )
    if has_vvip:
        builder.row(
            InlineKeyboardButton(text="🖤 Чёрный рынок", callback_data="black_market"),
        )
    builder.row(
        InlineKeyboardButton(text="💳 Донат",        callback_data="donate_menu"),
    )
    builder.row(
        InlineKeyboardButton(text="⚙️ Настройки",   callback_data="settings"),
    )
    return builder.as_markup()


def back_kb(callback: str = "main_menu") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=callback))
    return builder.as_markup()


def confirm_kb(yes_cb: str, no_cb: str = "main_menu") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да",  callback_data=yes_cb),
        InlineKeyboardButton(text="❌ Нет", callback_data=no_cb),
    )
    return builder.as_markup()