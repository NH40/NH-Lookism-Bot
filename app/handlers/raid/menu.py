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
)
from app.utils.formatters import fmt_num

router = Router()


# ── Главное меню рейдов ─────────────────────────────────────────────────────

@router.callback_query(F.data == "raid_menu")
async def cb_raid_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    # Проверка кредитной блокировки
    from app.services.bank.credits_service import credits_service
    block_msg = await credits_service.block_message(session, user.id)
    if block_msg:
        from app.utils.keyboards.common import back_kb
        try:
            await cb.message.edit_text(block_msg, reply_markup=back_kb("bank_credits"), parse_mode="HTML")
        except Exception:
            pass
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

    ui_str = f"УИ {user.ui_level} уровень" if user.ui_level > 0 else "нет УИ"
    donat_str = " (донат 🔱)" if user.ui_is_donat else ""
    path_frags = getattr(user, "path_fragments", 0)
    path_str = f" ({path_frags}/{PATH_SPIN_CRAFT_COST} для крутки)" if path_frags < PATH_SPIN_CRAFT_COST else " ✅ готово к крутке"
    from app.handlers.skills.med_genius import any_unlocked, _unlocked_count, MG_POTIONS, is_donat as _mg_is_donat
    if _mg_is_donat(user):
        mg_str = " ✅ Донат (все Ур.6)"
    elif any_unlocked(user):
        mg_str = f" {_unlocked_count(user)}/{len(MG_POTIONS)} зелий"
    else:
        mg_str = f" 🔒 ({user.alchemy_fragments}/30 🧪)"

    await cb.message.edit_text(
        f"⚔️ <b>Рейды</b>\n\n"
        f"🔮 Фрагменты УИ: <b>{user.ui_fragments}</b>\n"
        f"🧪 Фрагменты алхимии: <b>{user.alchemy_fragments}</b>\n"
        f"🔷 Фрагменты Пути: <b>{path_frags}</b>{path_str}\n"
        f"👁 УИ: {ui_str}{donat_str}\n"
        f"🩺 Гений медицины:{mg_str}\n\n"
        f"Выбери цель для рейда:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


# ── Выбор клана ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("raid_clan:"))
async def cb_raid_clan(cb: CallbackQuery, session: AsyncSession, user: User):
    clan_id = cb.data.split(":")[1]
    clan = raid_service.get_clan(clan_id)
    if not clan:
        await cb.answer("Клан не найден", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for boss_id, boss in clan["bosses"].items():
        cd_info = await raid_service.get_boss_cd_info(user.id, boss_id)
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

    await cb.message.edit_text(
        f"{clan['emoji']} <b>{clan['name']}</b>\n\n"
        f"{clan['description']}\n\n"
        f"{bosses_desc}\n\n"
        f"Выбери босса для рейда:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


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

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👁 Крафт УИ",          callback_data="craft_ui_menu"))
    builder.row(InlineKeyboardButton(text="🩺 Гений медицины",    callback_data="craft_mg_menu"))
    builder.row(InlineKeyboardButton(text="🔷 Крафт Пути",        callback_data="craft_path_menu"))
    builder.row(InlineKeyboardButton(text="◀️ Назад",             callback_data="raid_menu"))

    await cb.message.edit_text(
        f"🔨 <b>Крафт</b>\n\n"
        f"🔮 Фрагменты УИ: <b>{user.ui_fragments}</b>\n"
        f"🧪 Фрагменты алхимии: <b>{user.alchemy_fragments}</b>\n"
        f"🔷 Фрагменты Пути: <b>{path_frags}</b>\n\n"
        f"👁 УИ: <b>{ui_str}</b>\n"
        f"🩺 Гений медицины: <b>{mg_str}</b>\n"
        f"🔷 Уровень пути: <b>{path_level}/{PATH_LEVEL_MAX}</b>\n\n"
        f"Выбери раздел крафта:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "noop_raid")
async def cb_noop_raid(cb: CallbackQuery):
    await cb.answer()
