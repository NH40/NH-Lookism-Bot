from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def deck_kb(
    tickets: int,
    max_tickets: int,
    ticket_cd: int = 0,
) -> InlineKeyboardMarkup:
    from app.utils.formatters import fmt_ttl
    builder = InlineKeyboardBuilder()
    cd_text = f"⏳ {fmt_ttl(ticket_cd)}" if ticket_cd > 0 else "🎟 Получить тикет"
    builder.row(InlineKeyboardButton(text=cd_text, callback_data="try_ticket"))
    if tickets > 0:
        builder.row(
            InlineKeyboardButton(text="🎰 Прокрутить (1)", callback_data="pull_one"),
            InlineKeyboardButton(text="🎰 Все",            callback_data="pull_all"),
        )
    builder.row(InlineKeyboardButton(text="📚 Коллекция", callback_data="collection"))
    builder.row(InlineKeyboardButton(text="◀️ Назад",     callback_data="main_menu"))
    return builder.as_markup()