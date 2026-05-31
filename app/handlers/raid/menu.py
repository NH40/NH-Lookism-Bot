from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.models.user import User
from app.services.raid_service import raid_service
from app.services.cooldown_service import cooldown_service
from app.constants.raid import (
    RAID_BOSSES,
    PATH_SPIN_CRAFT_COST,
    PATH_LEVEL_MAX,
    PATH_LEVEL_COSTS,
    PATH_LEVEL_BONUSES,
    UI_CRAFT_COST,
    UI_LEVEL_PERKS,
    BUSINESS_DISTRICT_COST,
    BUSINESS_DISTRICTS_MAX,
)
from app.utils.formatters import fmt_num
from app.handlers.raid.boss import _send_or_edit_raid_photo

router = Router()


# ── Главное меню рейдов ─────────────────────────────────────────────────────

@router.callback_query(F.data == "raid_menu")
async def cb_raid_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    # Проверка кредитной блокировки
    from app.services.bank.credits_service import credits_service
    block_msg = await credits_service.block_message(session, user.id)
    if block_msg:
        from app.utils.keyboards.common import back_kb
        await _send_or_edit_raid_photo(cb, None, block_msg, back_kb("bank_credits"))
        await cb.answer()
        return

    active = await raid_service.get_active_raid(session, user.id)

    builder = InlineKeyboardBuilder()

    if active:
        now = datetime.now(timezone.utc)
        remaining = max(0, int((active.ends_at - now).total_seconds()))
        boss = raid_service.get_boss(active.clan_id, active.boss_id)
        boss_name = boss["name"] if boss else active.boss_id
        if remaining > 0:
            builder.row(InlineKeyboardButton(
                text=f"⚔️ {boss_name} — ⏳ {cooldown_service.format_ttl(remaining)}",
                callback_data=f"raid_status:{active.id}"
            ))
        else:
            builder.row(InlineKeyboardButton(
                text=f"✅ Получить награду за рейд на {boss_name}!",
                callback_data=f"raid_claim:{active.id}"
            ))
    else:
        for clan_id, clan in RAID_BOSSES.items():
            builder.row(InlineKeyboardButton(
                text=f"{clan['emoji']} {clan['name']}",
                callback_data=f"raid_clan:{clan_id}"
            ))

    builder.row(InlineKeyboardButton(
        text="🔨 Крафт", callback_data="raid_craft"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data="main_menu"
    ))

    ui_str = f"Ур.{user.ui_level}" if user.ui_level > 0 else ("Донат 🔱" if user.ui_is_donat else "нет")
    path_frags = getattr(user, "path_fragments", 0)
    biz_frags = getattr(user, "business_fragments", 0)
    from app.handlers.skills.med_genius import any_unlocked, _unlocked_count, MG_POTIONS, is_donat as _mg_is_donat
    if _mg_is_donat(user):
        mg_str = "Донат (все Ур.6)"
    elif any_unlocked(user):
        mg_str = f"{_unlocked_count(user)}/{len(MG_POTIONS)} зелий"
    else:
        mg_str = f"🔒 ({user.alchemy_fragments}/30 🧪)"

    menu_text = (
        f"⚔️ <b>Рейды</b>\n\n"
        f"<b>Фрагменты:</b>\n"
        f"🔮 УИ: <b>{user.ui_fragments}</b>   "
        f"🧪 Алхимия: <b>{user.alchemy_fragments}</b>\n"
        f"🔷 Путь: <b>{path_frags}</b>   "
        f"🏢 Бизнес: <b>{biz_frags}</b>\n\n"
        f"<b>Прокачка:</b>\n"
        f"👁 УИ: {ui_str}\n"
        f"🩺 Гений медицины: {mg_str}\n\n"
        f"Выбери цель для рейда:"
    )
    await _send_or_edit_raid_photo(cb, None, menu_text, builder.as_markup())


# ── Выбор клана ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("raid_clan:"))
async def cb_raid_clan(cb: CallbackQuery, session: AsyncSession, user: User):
    clan_id = cb.data.split(":")[1]
    clan = raid_service.get_clan(clan_id)
    if not clan:
        await cb.answer("Клан не найден", show_alert=True)
        return

    boss_ids = list(clan["bosses"].keys())
    cd_infos = await raid_service.get_bosses_cd_info_batch(user.id, boss_ids)

    builder = InlineKeyboardBuilder()
    for boss_id, boss in clan["bosses"].items():
        cd_info = cd_infos[boss_id]
        if cd_info["on_cd"]:
            ttl_str = cooldown_service.format_ttl(cd_info["ttl"])
            builder.row(InlineKeyboardButton(
                text=f"{boss['emoji']} {boss['name']} — ⏳ {ttl_str}",
                callback_data="noop_raid"
            ))
        else:
            builder.row(InlineKeyboardButton(
                text=f"{boss['emoji']} {boss['name']}",
                callback_data=f"raid_boss:{clan_id}:{boss_id}"
            ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data="raid_menu"
    ))

    bosses_desc = "\n\n".join(
        f"{boss['emoji']} <b>{boss['name']}</b>\n{boss['description']}"
        for boss in clan["bosses"].values()
    )

    clan_text = (
        f"{clan['emoji']} <b>{clan['name']}</b>\n\n"
        f"{clan['description']}\n\n"
        f"{bosses_desc}\n\n"
        f"Выбери босса для рейда:"
    )
    await _send_or_edit_raid_photo(cb, None, clan_text, builder.as_markup())


# ── Крафт — главное меню ──────────────────────────────────────────────────────

@router.callback_query(F.data == "raid_craft")
async def cb_raid_craft(cb: CallbackQuery, session: AsyncSession, user: User):
    path_frags = getattr(user, "path_fragments", 0)
    path_level = getattr(user, "skill_path_level", 0)
    ui_str = f"УИ {user.ui_level}" if user.ui_level > 0 else ("Донат 🔱" if user.ui_is_donat else "нет")
    from app.handlers.skills.med_genius import any_unlocked, _unlocked_count, MG_POTIONS, is_donat as _mg_is_donat
    if _mg_is_donat(user):
        mg_str = "✅ Донат (все Ур.6)"
    elif any_unlocked(user):
        mg_str = f"{_unlocked_count(user)}/{len(MG_POTIONS)} зелий"
    else:
        mg_str = f"🔒 ({user.alchemy_fragments}/30 🧪)"

    biz_frags = getattr(user, "business_fragments", 0)
    bonus_districts = getattr(user, "bonus_business_districts", 0)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👁 Крафт УИ",          callback_data="craft_ui_menu"))
    builder.row(InlineKeyboardButton(text="🩺 Гений медицины",    callback_data="craft_mg_menu"))
    builder.row(InlineKeyboardButton(text="🔷 Крафт Пути",        callback_data="craft_path_menu"))
    builder.row(InlineKeyboardButton(text="🏢 Бизнес-крафт",      callback_data="craft_biz_menu"))
    builder.row(InlineKeyboardButton(text="💱 Обменник",           callback_data="craft_exchange_menu"))
    builder.row(InlineKeyboardButton(text="◀️ Назад",             callback_data="raid_menu"))

    war_points = getattr(user, "war_points", 0)
    war_genius = getattr(user, "war_genius_level", 0)
    craft_text = (
        f"🔨 <b>Крафт</b>\n\n"
        f"<b>Ресурсы:</b>\n"
        f"🔮 УИ: <b>{user.ui_fragments}</b>   "
        f"🧪 Алхимия: <b>{user.alchemy_fragments}</b>\n"
        f"🔷 Путь: <b>{path_frags}</b>   "
        f"🏢 Бизнес: <b>{biz_frags}</b>\n"
        f"⚔️ Очки войны: <b>{war_points}</b>\n\n"
        f"<b>Прогресс:</b>\n"
        f"👁 УИ: <b>{ui_str}</b>   "
        f"⚔️ Гений войны: <b>{war_genius}/5</b>\n"
        f"🩺 Гений медицины: <b>{mg_str}</b>\n"
        f"🔷 Уровень пути: <b>{path_level}/{PATH_LEVEL_MAX}</b>   "
        f"🏘 Районов: <b>{bonus_districts}/{BUSINESS_DISTRICTS_MAX}</b>\n\n"
        f"Выбери раздел:"
    )
    await _send_or_edit_raid_photo(cb, None, craft_text, builder.as_markup())


@router.callback_query(F.data == "noop_raid")
async def cb_noop_raid(cb: CallbackQuery):
    await cb.answer()
