from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def squad_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💪 Усилить отряд",    callback_data="do_train"))
    builder.row(InlineKeyboardButton(text="📢 Вербовка в отряд", callback_data="do_recruit"))
    builder.row(InlineKeyboardButton(text="🗒 Состав армии",      callback_data="squad_list"))
    builder.row(InlineKeyboardButton(text="◀️ Назад",            callback_data="main_menu"))
    return builder.as_markup()


def ranks_kb(available_ranks: list[str]) -> InlineKeyboardMarkup:
    from app.data.squad import RANKS_BY_ID
    builder = InlineKeyboardBuilder()
    for rank in available_ranks:
        cfg = RANKS_BY_ID.get(rank)
        if cfg:
            builder.button(
                text=f"{rank} — {cfg.base_power:,} силы",
                callback_data=f"recruit_rank:{rank}"
            )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="squad"))
    return builder.as_markup()