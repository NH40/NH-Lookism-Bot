from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_kb() -> InlineKeyboardMarkup:
    """Главный хаб — 5 категорий, каждая открывает своё подменю с кнопками."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⚔️ Бой",        callback_data="menu_combat"))
    builder.row(InlineKeyboardButton(text="💰 Экономика",  callback_data="menu_economy"))
    builder.row(InlineKeyboardButton(text="📈 Прогресс",   callback_data="menu_progress"))
    builder.row(InlineKeyboardButton(text="🏯 Социальное", callback_data="menu_social"))
    builder.row(InlineKeyboardButton(text="⚙️ Прочее",     callback_data="menu_other"))
    return builder.as_markup()


def menu_combat_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⚔️ Атака",       callback_data="attack"),
        InlineKeyboardButton(text="⚔️ Рейд",         callback_data="raid_menu"),
    )
    builder.row(
        InlineKeyboardButton(text="👹 Боссы",        callback_data="bosses_menu"),
        InlineKeyboardButton(text="🗺 Походы",       callback_data="campaigns_menu"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
    return builder.as_markup()


def menu_economy_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏢 Бизнес",       callback_data="business"),
        InlineKeyboardButton(text="🏦 Банк",         callback_data="bank_menu"),
    )
    builder.row(
        InlineKeyboardButton(text="🛒 Магазин",      callback_data="shop"),
        InlineKeyboardButton(text="🏪 Биржа",        callback_data="market_menu"),
    )
    builder.row(
        InlineKeyboardButton(text="🏛 Аукцион",      callback_data="auction"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
    return builder.as_markup()


def menu_progress_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👥 Группировка",  callback_data="squad"),
        InlineKeyboardButton(text="🃏 Колода",       callback_data="deck"),
    )
    builder.row(
        InlineKeyboardButton(text="🏆 Титулы",       callback_data="titles"),
        InlineKeyboardButton(text="⚡ Навыки",       callback_data="skills"),
    )
    builder.row(
        InlineKeyboardButton(text="🏋 Тренировка",   callback_data="training_menu"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
    return builder.as_markup()


def menu_social_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏯 Кланы",        callback_data="clans_menu"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
    return builder.as_markup()


def menu_other_kb(has_vvip: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📋 Задания",      callback_data="daily_quests"),
        InlineKeyboardButton(text="💳 Донат",        callback_data="donate_menu"),
    )
    if has_vvip:
        builder.row(
            InlineKeyboardButton(text="🖤 Чёрный рынок", callback_data="black_market"),
        )
    builder.row(
        InlineKeyboardButton(text="⚙️ Настройки",   callback_data="settings"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
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