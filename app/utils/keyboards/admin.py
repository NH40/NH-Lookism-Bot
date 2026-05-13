from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_main_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    builder.row(InlineKeyboardButton(text="🔍 Найти игрока", callback_data="admin_find"))
    builder.row(InlineKeyboardButton(text="🔧 Патч", callback_data="admin_patch"))
    builder.row(InlineKeyboardButton(text="🎁 Промокоды", callback_data="admin_promos"))
    builder.row(InlineKeyboardButton(text="🏯 Клан-донат", callback_data="admin_clan_donat"))
    builder.row(InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"))
    builder.row(InlineKeyboardButton(text="👥 Действия со всеми", callback_data="admin_bulk"))
    builder.row(InlineKeyboardButton(text="💾 Бэкапы", callback_data="admin_backup"))
    return builder.as_markup()


def admin_user_kb(tg_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💎 Выдать титул", callback_data=f"adm_title:{tg_id}"),
        InlineKeyboardButton(text="❌ Снять титул", callback_data=f"adm_untitle:{tg_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="💰 Монеты", callback_data=f"adm_coins:{tg_id}"),
        InlineKeyboardButton(text="🎟 Тикеты", callback_data=f"adm_tickets:{tg_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="📦 Ресурсы", callback_data=f"adm_resources:{tg_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="⭐ Абсолютный перс", callback_data=f"adm_chars:{tg_id}"),
        InlineKeyboardButton(text="👥 Статист", callback_data=f"adm_squads:{tg_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="👁 TUI", callback_data=f"adm_tui:{tg_id}"),
        InlineKeyboardButton(text="❌ Убрать TUI", callback_data=f"adm_untui:{tg_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="⭐ Пробуждение +1", callback_data=f"adm_prestige:{tg_id}"),
        InlineKeyboardButton(text="⭐ Пробуждение -1", callback_data=f"adm_unprestige:{tg_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🔱 Ебать (всё)", callback_data=f"adm_all:{tg_id}"),
        InlineKeyboardButton(text="💀 Лох (снять)", callback_data=f"adm_none:{tg_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить аккаунт", callback_data=f"adm_delete_confirm:{tg_id}"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_main"))
    return builder.as_markup()


def titles_grant_kb(tg_id: int) -> InlineKeyboardMarkup:
    from app.data.titles import DONAT_SETS
    builder = InlineKeyboardBuilder()
    for s in DONAT_SETS:
        builder.button(
            text=f"📦 {s.name} — {s.price_rub}₽",
            callback_data=f"adm_grantset:{tg_id}:{s.set_id}"
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data=f"adm_user:{tg_id}"
    ))
    return builder.as_markup()