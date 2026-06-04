from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_main_kb(maintenance_on: bool = False):
    builder = InlineKeyboardBuilder()
    maint_text = "🔴 Тех.режим: ВКЛ" if maintenance_on else "🟢 Тех.режим: ВЫКЛ"
    builder.row(
        InlineKeyboardButton(text=maint_text, callback_data="admin_maintenance_toggle"),
    )
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton(text="🔍 Найти игрока", callback_data="admin_find"),
    )
    builder.row(
        InlineKeyboardButton(text="🔧 Патч", callback_data="admin_patch"),
        InlineKeyboardButton(text="🎁 Промокоды", callback_data="admin_promos"),
        InlineKeyboardButton(text="💾 Бэкапы", callback_data="admin_backup"),
    )
    builder.row(
        InlineKeyboardButton(text="🏯 Клан-донат", callback_data="admin_clan_donat"),
        InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"),
        InlineKeyboardButton(text="👥 Все игроки", callback_data="admin_bulk"),
    )
    builder.row(
        InlineKeyboardButton(text="👁 Реальный топ (вкл. скрытых)", callback_data="admin_real_top"),
    )
    return builder.as_markup()


def admin_user_kb(tg_id: int, donat_duel_cd: bool = False, is_banned: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    # ── Титулы ──────────────────────────────────────────────────────────────
    builder.row(
        InlineKeyboardButton(text="💎 Выдать титул", callback_data=f"adm_title:{tg_id}"),
        InlineKeyboardButton(text="❌ Снять титул", callback_data=f"adm_untitle:{tg_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🔱 Все титулы", callback_data=f"adm_all:{tg_id}"),
        InlineKeyboardButton(text="💀 Снять все", callback_data=f"adm_none:{tg_id}"),
    )

    # ── Ресурсы ──────────────────────────────────────────────────────────────
    builder.row(
        InlineKeyboardButton(text="💰 Монеты", callback_data=f"adm_coins:{tg_id}"),
        InlineKeyboardButton(text="🎟 Тикеты", callback_data=f"adm_tickets:{tg_id}"),
        InlineKeyboardButton(text="📦 Ресурсы", callback_data=f"adm_resources:{tg_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="💳 NHDonate", callback_data=f"adm_donate:{tg_id}"),
    )

    # ── Армия и карты ────────────────────────────────────────────────────────
    builder.row(
        InlineKeyboardButton(text="👥 Статист", callback_data=f"adm_squads:{tg_id}"),
        InlineKeyboardButton(text="🃏 Карточки ▼", callback_data=f"adm_cards_menu:{tg_id}"),
        InlineKeyboardButton(text="💎 Дать пыль", callback_data=f"adm_give_dust:{tg_id}"),
    )

    # ── Города ───────────────────────────────────────────────────────────────
    builder.row(
        InlineKeyboardButton(text="🏙 +Город", callback_data=f"adm_give_city:{tg_id}"),
        InlineKeyboardButton(text="🏚 −Все города", callback_data=f"adm_take_cities:{tg_id}"),
    )

    # ── Пробуждения ──────────────────────────────────────────────────────────
    builder.row(
        InlineKeyboardButton(text="⭐ +Пробуждение", callback_data=f"adm_prestige:{tg_id}"),
        InlineKeyboardButton(text="⭐ −Пробуждение", callback_data=f"adm_unprestige:{tg_id}"),
    )

    # ── Круговые донаты ───────────────────────────────────────────────────────
    builder.row(
        InlineKeyboardButton(text="🔄 Круговые донаты", callback_data=f"adm_circ_menu:{tg_id}"),
    )

    # ── Очистка ──────────────────────────────────────────────────────────────
    builder.row(
        InlineKeyboardButton(text="🏗 Здания", callback_data=f"adm_clear_buildings:{tg_id}"),
        InlineKeyboardButton(text="🗑 Удалить аккаунт", callback_data=f"adm_delete_confirm:{tg_id}"),
    )

    # ── Бан ──────────────────────────────────────────────────────────────────
    ban_label = "✅ Разбанить" if is_banned else "🔨 Забанить"
    if is_banned:
        builder.row(
            InlineKeyboardButton(text="🔨 Изм. бан", callback_data=f"adm_ban:{tg_id}"),
            InlineKeyboardButton(text="✅ Разбанить", callback_data=f"adm_unban:{tg_id}"),
        )
    else:
        builder.row(
            InlineKeyboardButton(text="🔨 Забанить", callback_data=f"adm_ban:{tg_id}"),
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
