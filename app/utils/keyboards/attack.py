from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def sector_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    sectors = ["Н", "Х", "Ч", "Б", "М", "Ж"]
    for s in sectors:
        builder.button(text=f"🌐 Сектор {s}", callback_data=f"choose_sector:{s}")
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
    return builder.as_markup()


def cities_kb(cities: list, prefix: str = "choose_city") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for city in cities:
        status = "✅" if city.is_fully_captured else f"{city.captured_districts}/{city.total_districts}"
        builder.button(
            text=f"{city.name} [{status}]",
            callback_data=f"{prefix}:{city.id}"
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="attack"))
    return builder.as_markup()


def attack_action_kb(
    has_pvp: bool = False,
    cd_seconds: int = 0,
    extra_attacks: int = 0,
) -> InlineKeyboardMarkup:
    from app.utils.formatters import fmt_ttl
    builder = InlineKeyboardBuilder()
    if cd_seconds > 0:
        builder.row(InlineKeyboardButton(
            text=f"⏳ КД: {fmt_ttl(cd_seconds)}",
            callback_data="attack_cd"
        ))
    else:
        builder.row(InlineKeyboardButton(
            text="⚔️ Атаковать",
            callback_data="do_attack"
        ))
        if extra_attacks > 0:
            builder.row(InlineKeyboardButton(
                text=f"⚡ Доп. атака ({extra_attacks})",
                callback_data="do_attack"
            ))
    if has_pvp:
        builder.row(InlineKeyboardButton(
            text="🥊 PvP",
            callback_data="pvp_attack"
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="attack"))
    return builder.as_markup()