from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.models.user import User
from app.services.raid_service import raid_service
from app.services.cooldown_service import cooldown_service
from app.constants.raid import (
    RAID_BOSSES, UI_CRAFT_COST, UI_LEVEL_PERKS,
    ALCHEMY_CRAFT_COST,
)
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_num

router = Router()


# ── Главное меню рейдов ─────────────────────────────────────────────────────

@router.callback_query(F.data == "raid_menu")
async def cb_raid_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    # Проверяем активный рейд
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
    alchemy_str = " ✅" if user.donat_ui_potion else f" ({user.alchemy_fragments}/{ALCHEMY_CRAFT_COST})"

    await cb.message.edit_text(
        f"⚔️ <b>Рейды</b>\n\n"
        f"🔮 Фрагменты УИ: <b>{user.ui_fragments}</b>\n"
        f"🧪 Фрагменты алхимии: <b>{user.alchemy_fragments}</b>{alchemy_str}\n"
        f"👁 УИ: {ui_str}{donat_str}\n\n"
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

    # Формируем описание боссов из константы
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


# ── Информация о боссе ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("raid_boss:"))
async def cb_raid_boss(cb: CallbackQuery, session: AsyncSession, user: User):
    parts = cb.data.split(":")
    clan_id, boss_id = parts[1], parts[2]
    boss = raid_service.get_boss(clan_id, boss_id)
    if not boss:
        await cb.answer("Босс не найден", show_alert=True)
        return

    # Считаем мощь игрока для этого босса
    power = await raid_service.get_user_power_for_boss(session, user, boss["damage_source"])
    if boss["damage_source"] == "squad":
        source_name = "статистов"
    elif boss["damage_source"] == "combat_power":
        source_name = "боевой мощи (÷2)"
    else:
        source_name = "уникальных персонажей"

    reward_line = (
        "🧪 Награда: фрагменты алхимии (макс 25)"
        if boss.get("reward_fragments") == "alchemy"
        else "🔮 Награда: фрагменты УИ"
    )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"⚔️ Начать рейд",
        callback_data=f"raid_start:{clan_id}:{boss_id}"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data=f"raid_clan:{clan_id}"
    ))

    await cb.message.edit_text(
        f"{boss['emoji']} <b>{boss['name']}</b>\n\n"
        f"📖 {boss['description']}\n\n"
        f"💪 Ваша мощь ({source_name}): <b>{fmt_num(power)}</b>\n"
        f"🎯 HP босса: {fmt_num(boss['base_hp'])}\n"
        f"⏱ Длительность рейда: 1 час\n"
        f"⏳ КД после рейда: {boss['cd_hours']} часов\n"
        f"{reward_line}\n\n"
        f"После начала рейда у тебя есть 1 час\n"
        f"чтобы нанести максимум урона!",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


# ── Старт рейда ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("raid_start:"))
async def cb_raid_start(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.services.cooldown_service import cooldown_service
    lock_key = cooldown_service.raid_lock_key(user.id)
    if not await cooldown_service.acquire_lock(lock_key, ttl=10):
        await cb.answer("Подожди...", show_alert=False)
        return

    parts = cb.data.split(":")
    clan_id, boss_id = parts[1], parts[2]

    result = await raid_service.start_raid(session, user, clan_id, boss_id)
    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    ends_at = result["ends_at"]
    await cb.message.edit_text(
        f"⚔️ <b>Рейд начался!</b>\n\n"
        f"👹 Босс: {result['boss_name']}\n"
        f"💥 Нанесённый урон: <b>{fmt_num(result['damage'])}</b>\n\n"
        f"⏱ Рейд завершится через: <b>{result['duration_hours']} час</b>\n"
        f"🕐 Время окончания: {ends_at.strftime('%H:%M')}\n\n"
        f"По истечении времени вернись сюда\n"
        f"чтобы получить фрагменты УИ!",
        reply_markup=back_kb("raid_menu"),
        parse_mode="HTML",
    )


# ── Статус рейда ─────────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("raid_status:"))
async def cb_raid_status(cb: CallbackQuery, session: AsyncSession, user: User):
    raid_id = int(cb.data.split(":")[1])
    from app.models.raid import RaidSession
    from sqlalchemy import select as sa_select
    result = await session.execute(
        sa_select(RaidSession).where(RaidSession.id == raid_id)
    )
    raid = result.scalar_one_or_none()
    if not raid:
        await cb.answer("Рейд не найден", show_alert=True)
        return

    now = datetime.now(timezone.utc)
    remaining = max(0, int((raid.ends_at - now).total_seconds()))
    boss = raid_service.get_boss(raid.clan_id, raid.boss_id)

    # Проверяем КД атаки
    attack_cd = await raid_service.get_attack_cd_info(raid_id, user.id)

    builder = InlineKeyboardBuilder()

    if remaining == 0:
        builder.row(InlineKeyboardButton(
            text="🎁 Получить награду!",
            callback_data=f"raid_claim:{raid_id}"
        ))
    else:
        if attack_cd["on_cd"]:
            ttl_str = cooldown_service.format_ttl(attack_cd["ttl"])
            builder.row(InlineKeyboardButton(
                text=f"⚔️ Атака — ⏳ {ttl_str}",
                callback_data="noop_raid"
            ))
        else:
            builder.row(InlineKeyboardButton(
                text="⚔️ Атаковать босса!",
                callback_data=f"raid_attack:{raid_id}"
            ))

    builder.row(InlineKeyboardButton(
        text="🔄 Обновить", callback_data=f"raid_status:{raid_id}"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data="raid_menu"
    ))

    boss_name = boss["name"] if boss else raid.boss_id
    boss_hp = boss["base_hp"] if boss else 0

    # Считаем процент урона от HP
    damage_pct = min(100.0, (raid.damage_dealt / boss_hp * 100)) if boss_hp > 0 else 0
    hp_bar_filled = int(damage_pct / 10)
    hp_bar = "🟥" * hp_bar_filled + "⬛" * (10 - hp_bar_filled)

    await cb.message.edit_text(
        f"⚔️ <b>Активный рейд — {boss_name}</b>\n\n"
        f"❤️ HP босса: {fmt_num(boss_hp)}\n"
        f"💥 Нанесённый урон: <b>{fmt_num(raid.damage_dealt)}</b> ({damage_pct:.1f}%)\n"
        f"{hp_bar}\n"
        f"🗡 Атак совершено: <b>{raid.attack_count}</b>\n\n"
        + (f"⏳ До конца рейда: {cooldown_service.format_ttl(remaining)}"
           if remaining > 0 else "✅ Рейд завершён! Забери награду.")
        + ("\n\n⚔️ Атакуй снова чтобы накопить больше урона!" if remaining > 0 and not attack_cd["on_cd"] else ""),
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )

# ── Получение награды ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("raid_claim:"))
async def cb_raid_claim(cb: CallbackQuery, session: AsyncSession, user: User):
    raid_id = int(cb.data.split(":")[1])
    result = await raid_service.finish_raid(session, user, raid_id)

    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    is_alchemy = result.get("reward_type") == "alchemy"
    frag_emoji = "🧪" if is_alchemy else "🔮"
    frag_name = "фрагментов алхимии" if is_alchemy else "фрагментов УИ"

    await cb.message.edit_text(
        f"🎉 <b>Рейд завершён!</b>\n\n"
        f"👹 Босс: {result['boss_name']}\n"
        f"💥 Нанесённый урон: <b>{fmt_num(result['damage'])}</b>\n\n"
        f"{frag_emoji} Получено {frag_name}: <b>+{result['fragments']}</b>\n"
        f"📊 Всего: <b>{result['total_fragments']}</b>\n\n"
        f"Используй фрагменты в <b>Рейды → Крафт</b>!",
        reply_markup=back_kb("raid_menu"),
        parse_mode="HTML",
    )


# ── Крафт УИ ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "raid_craft")
async def cb_raid_craft(cb: CallbackQuery, session: AsyncSession, user: User):
    builder = InlineKeyboardBuilder()

    # ── Секция УИ ────────────────────────────────────────────────────────────
    if user.ui_is_donat:
        builder.row(InlineKeyboardButton(
            text="🔱 УИ (Донат) — Максимальный уровень",
            callback_data="noop_raid"
        ))
    else:
        for level, cost in UI_CRAFT_COST.items():
            perk = UI_LEVEL_PERKS[level]
            if user.ui_level >= level:
                builder.row(InlineKeyboardButton(
                    text=f"✅ {perk['name']} — {perk['perk']}",
                    callback_data="noop_raid"
                ))
            else:
                can = "✅" if user.ui_fragments >= cost else "❌"
                builder.row(InlineKeyboardButton(
                    text=f"{can} {perk['name']} — {cost} фр. УИ",
                    callback_data=f"craft_ui:{level}"
                ))

    # ── Секция УИ Алхимии ────────────────────────────────────────────────────
    if user.donat_ui_potion:
        builder.row(InlineKeyboardButton(
            text="✅ УИ Алхимии — Авто-зелья",
            callback_data="noop_raid"
        ))
    else:
        can_alchemy = "✅" if user.alchemy_fragments >= ALCHEMY_CRAFT_COST else "❌"
        builder.row(InlineKeyboardButton(
            text=f"{can_alchemy} УИ Алхимии — {ALCHEMY_CRAFT_COST} фр. алхимии",
            callback_data="craft_alchemy_ui"
        ))

    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data="raid_menu"
    ))

    ui_str = f"УИ {user.ui_level} уровень" if user.ui_level > 0 else "нет"
    alchemy_ui_str = "✅ Получен" if user.donat_ui_potion else f"❌ Нужно {ALCHEMY_CRAFT_COST} фр."
    lines = [
        f"🔮 <b>Крафт</b>\n\n"
        f"Фрагменты УИ: <b>{user.ui_fragments}</b>\n"
        f"Фрагменты алхимии: <b>{user.alchemy_fragments}</b>\n"
        f"Текущий УИ: <b>{ui_str}</b>\n\n"
        f"<b>Уровни УИ:</b>\n"
    ]
    for lvl, perk in UI_LEVEL_PERKS.items():
        cost = UI_CRAFT_COST[lvl]
        status = "✅" if user.ui_level >= lvl else f"{cost} фр."
        lines.append(f"  {perk['name']}: {perk['perk']} [{status}]")
    lines.append(f"\n<b>УИ Алхимии:</b>")
    lines.append(f"  🧪 Авто-покупка всех зелий по КД [{alchemy_ui_str}]")

    await cb.message.edit_text(
        "\n".join(lines),
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("craft_ui:"))
async def cb_craft_ui(cb: CallbackQuery, session: AsyncSession, user: User):
    level = int(cb.data.split(":")[1])
    result = await raid_service.craft_ui(session, user, level)

    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    perk = UI_LEVEL_PERKS[level]
    await cb.answer(f"✅ {perk['name']} получен! {perk['perk']}", show_alert=True)
    await cb_raid_craft(cb, session, user)


@router.callback_query(F.data == "craft_alchemy_ui")
async def cb_craft_alchemy_ui(cb: CallbackQuery, session: AsyncSession, user: User):
    result = await raid_service.craft_alchemy_ui(session, user)

    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    await cb.answer(
        "✅ УИ Алхимии получен!\n🧪 Авто-зелья активированы!",
        show_alert=True
    )
    await cb_raid_craft(cb, session, user)


@router.callback_query(F.data.startswith("raid_attack:"))
async def cb_raid_attack(cb: CallbackQuery, session: AsyncSession, user: User):
    raid_id = int(cb.data.split(":")[1])
    result = await raid_service.attack_boss(session, user, raid_id)

    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    if result.get("boss_killed"):
        is_alchemy = result.get("reward_type") == "alchemy"
        frag_emoji = "🧪" if is_alchemy else "🔮"
        frag_name = "фрагментов алхимии" if is_alchemy else "фрагментов УИ"
        await cb.answer(
            f"💀 Босс повержен!\n"
            f"{frag_emoji} Получено: +{result['fragments']}",
            show_alert=True
        )
        await cb.message.edit_text(
            f"🎉 <b>Босс {result['boss_name']} повержен!</b>\n\n"
            f"💥 Суммарный урон: <b>{fmt_num(result['total_damage'])}</b>\n"
            f"🗡 Атак совершено: <b>{result['attack_count']}</b>\n\n"
            f"{frag_emoji} Получено {frag_name}: <b>+{result['fragments']}</b>\n"
            f"📊 Всего: <b>{result['total_fragments']}</b>\n\n"
            f"Используй фрагменты в <b>Рейды → Крафт</b>!",
            reply_markup=back_kb("raid_menu"),
            parse_mode="HTML",
        )
    else:
        await cb.answer(
            f"⚔️ +{fmt_num(result['damage'])} урона!\n"
            f"Всего: {fmt_num(result['total_damage'])}",
            show_alert=True
        )
        await cb_raid_status(cb, session, user)

@router.callback_query(F.data == "noop_raid")
async def cb_noop_raid(cb: CallbackQuery):
    await cb.answer()