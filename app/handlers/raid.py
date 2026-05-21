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
    ALCHEMY_CRAFT_COST, PATH_SPIN_CRAFT_COST,
    PATH_LEVEL_COSTS, PATH_LEVEL_MAX, PATH_LEVEL_BONUSES,
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
    path_frags = getattr(user, "path_fragments", 0)
    path_str = f" ({path_frags}/{PATH_SPIN_CRAFT_COST} для крутки)" if path_frags < PATH_SPIN_CRAFT_COST else " ✅ готово к крутке"

    await cb.message.edit_text(
        f"⚔️ <b>Рейды</b>\n\n"
        f"🔮 Фрагменты УИ: <b>{user.ui_fragments}</b>\n"
        f"🧪 Фрагменты алхимии: <b>{user.alchemy_fragments}</b>{alchemy_str}\n"
        f"🔷 Фрагменты Пути: <b>{path_frags}</b>{path_str}\n"
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
    divisor = boss.get("combat_power_divisor", 2)
    power = await raid_service.get_user_power_for_boss(session, user, boss["damage_source"], divisor)
    if boss["damage_source"] == "squad":
        source_name = "статистов"
    elif boss["damage_source"] == "combat_power":
        source_name = f"боевой мощи (÷{divisor})"
    else:
        source_name = "уникальных персонажей"

    reward_type = boss.get("reward_fragments")
    if reward_type == "alchemy":
        reward_line = "🧪 Награда: фрагменты алхимии (макс 25)"
    elif reward_type == "path":
        reward_line = "🔷 Награда: фрагменты Пути (макс 20)"
    else:
        reward_line = "🔮 Награда: фрагменты УИ"

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
    reward_type = result.get("reward_type", "ui")
    if reward_type == "alchemy":
        frag_line = "чтобы получить фрагменты алхимии!"
    elif reward_type == "path":
        frag_line = "чтобы получить фрагменты Пути!"
    else:
        frag_line = "чтобы получить фрагменты УИ!"
    await cb.message.edit_text(
        f"⚔️ <b>Рейд начался!</b>\n\n"
        f"👹 Босс: {result['boss_name']}\n"
        f"💥 Нанесённый урон: <b>{fmt_num(result['damage'])}</b>\n\n"
        f"⏱ Рейд завершится через: <b>{result['duration_hours']} час</b>\n"
        f"🕐 Время окончания: {ends_at.strftime('%H:%M')}\n\n"
        f"По истечении времени вернись сюда\n"
        f"{frag_line}",
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

    can_attack_now = remaining > 0 and not attack_cd["on_cd"]

    if remaining == 0:
        builder.row(InlineKeyboardButton(
            text="🎁 Получить награду!",
            callback_data=f"raid_claim:{raid_id}"
        ))
    else:
        if can_attack_now:
            builder.row(InlineKeyboardButton(
                text="⚔️ Атаковать босса!",
                callback_data=f"raid_attack:{raid_id}"
            ))
        else:
            ttl_str = cooldown_service.format_ttl(attack_cd["ttl"])
            builder.row(InlineKeyboardButton(
                text=f"⚔️ Атака — ⏳ {ttl_str}",
                callback_data="noop_raid"
            ))

    builder.row(InlineKeyboardButton(
        text="🔄 Обновить", callback_data=f"raid_status:{raid_id}"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data="raid_menu"
    ))

    boss_name = boss["name"] if boss else raid.boss_id
    boss_hp = boss["base_hp"] if boss else 0

    damage_pct = min(100.0, (raid.damage_dealt / boss_hp * 100)) if boss_hp > 0 else 0
    hp_bar_filled = int(damage_pct / 10)
    hp_bar = "🟥" * hp_bar_filled + "⬛" * (10 - hp_bar_filled)

    status_line = (
        f"⏳ До конца рейда: {cooldown_service.format_ttl(remaining)}"
        if remaining > 0 else "✅ Рейд завершён! Забери награду."
    )
    extra_line = ""
    if remaining > 0 and not attack_cd["on_cd"]:
        extra_line = "\n\n⚔️ Атакуй снова чтобы накопить больше урона!"

    await cb.message.edit_text(
        f"⚔️ <b>Активный рейд — {boss_name}</b>\n\n"
        f"❤️ HP босса: {fmt_num(boss_hp)}\n"
        f"💥 Нанесённый урон: <b>{fmt_num(raid.damage_dealt)}</b> ({damage_pct:.1f}%)\n"
        f"{hp_bar}\n"
        f"🗡 Атак совершено: <b>{raid.attack_count}</b>\n\n"
        + status_line + extra_line,
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

    reward_type = result.get("reward_type")
    if reward_type == "alchemy":
        frag_emoji, frag_name = "🧪", "фрагментов алхимии"
    elif reward_type == "path":
        frag_emoji, frag_name = "🔷", "фрагментов Пути"
    else:
        frag_emoji, frag_name = "🔮", "фрагментов УИ"

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


# ── Крафт — главное меню ──────────────────────────────────────────────────────

@router.callback_query(F.data == "raid_craft")
async def cb_raid_craft(cb: CallbackQuery, session: AsyncSession, user: User):
    path_frags = getattr(user, "path_fragments", 0)
    path_level = getattr(user, "skill_path_level", 0)
    ui_str = f"УИ {user.ui_level}" if user.ui_level > 0 else ("Донат 🔱" if user.ui_is_donat else "нет")

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👁 Крафт УИ",       callback_data="craft_ui_menu"))
    builder.row(InlineKeyboardButton(text="🧪 Крафт Алхимии",  callback_data="craft_alchemy_menu"))
    builder.row(InlineKeyboardButton(text="🔷 Крафт Пути",     callback_data="craft_path_menu"))
    builder.row(InlineKeyboardButton(text="◀️ Назад",          callback_data="raid_menu"))

    await cb.message.edit_text(
        f"🔨 <b>Крафт</b>\n\n"
        f"🔮 Фрагменты УИ: <b>{user.ui_fragments}</b>\n"
        f"🧪 Фрагменты алхимии: <b>{user.alchemy_fragments}</b>\n"
        f"🔷 Фрагменты Пути: <b>{path_frags}</b>\n\n"
        f"👁 УИ: <b>{ui_str}</b>\n"
        f"🧪 УИ Алхимии: <b>{'✅' if user.donat_ui_potion else '❌'}</b>\n"
        f"🔷 Уровень пути: <b>{path_level}/{PATH_LEVEL_MAX}</b>\n\n"
        f"Выбери раздел крафта:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


# ── Крафт УИ — подменю ────────────────────────────────────────────────────────

@router.callback_query(F.data == "craft_ui_menu")
async def cb_craft_ui_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    builder = InlineKeyboardBuilder()

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

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="raid_craft"))

    ui_str = f"УИ {user.ui_level} уровень" if user.ui_level > 0 else ("Донат 🔱" if user.ui_is_donat else "нет")
    lines = [
        f"👁 <b>Крафт УИ</b>\n",
        f"🔮 Фрагменты УИ: <b>{user.ui_fragments}</b>",
        f"Текущий УИ: <b>{ui_str}</b>\n",
    ]
    for lvl, perk in UI_LEVEL_PERKS.items():
        cost = UI_CRAFT_COST[lvl]
        st = "✅" if user.ui_level >= lvl else f"{cost} фр."
        lines.append(f"  {perk['name']}: {perk['perk']} [{st}]")

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
    await cb_craft_ui_menu(cb, session, user)


# ── Крафт Алхимии — подменю ───────────────────────────────────────────────────

@router.callback_query(F.data == "craft_alchemy_menu")
async def cb_craft_alchemy_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    builder = InlineKeyboardBuilder()

    if user.donat_ui_potion:
        builder.row(InlineKeyboardButton(
            text="✅ УИ Алхимии — Авто-зелья активны",
            callback_data="noop_raid"
        ))
    else:
        can = "✅" if user.alchemy_fragments >= ALCHEMY_CRAFT_COST else "❌"
        builder.row(InlineKeyboardButton(
            text=f"{can} УИ Алхимии — {ALCHEMY_CRAFT_COST} 🧪 фрагментов",
            callback_data="craft_alchemy_ui"
        ))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="raid_craft"))

    status = "✅ Получен — авто-зелья активны" if user.donat_ui_potion else f"❌ Нужно {ALCHEMY_CRAFT_COST} фр."
    await cb.message.edit_text(
        f"🧪 <b>Крафт Алхимии</b>\n\n"
        f"🧪 Фрагменты алхимии: <b>{user.alchemy_fragments}</b>\n\n"
        f"<b>УИ Алхимии:</b> {status}\n"
        f"<i>Автоматически покупает все зелья по кулдауну</i>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "craft_alchemy_ui")
async def cb_craft_alchemy_ui(cb: CallbackQuery, session: AsyncSession, user: User):
    result = await raid_service.craft_alchemy_ui(session, user)

    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    await cb.answer("✅ УИ Алхимии получен!\n🧪 Авто-зелья активированы!", show_alert=True)
    await cb_craft_alchemy_menu(cb, session, user)


# ── Крафт Пути — подменю ──────────────────────────────────────────────────────

@router.callback_query(F.data == "craft_path_menu")
async def cb_craft_path_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.services.skill_service import skill_service as _ss
    path_frags = getattr(user, "path_fragments", 0)
    path_level = getattr(user, "skill_path_level", 0)
    slots = getattr(user, "extra_path_skill_slots", 1)
    extra_count = await _ss.get_extra_path_skills_count(session, user) if user.skill_path else 0
    slots_full = extra_count >= slots

    builder = InlineKeyboardBuilder()

    # Уровень пути
    if path_level >= PATH_LEVEL_MAX:
        builder.row(InlineKeyboardButton(
            text=f"✅ Уровень пути — МАКСИМУМ ({PATH_LEVEL_MAX}/{PATH_LEVEL_MAX})",
            callback_data="noop_raid"
        ))
    elif user.skill_path:
        next_cost = PATH_LEVEL_COSTS[path_level]
        can = "✅" if path_frags >= next_cost else "❌"
        builder.row(InlineKeyboardButton(
            text=f"{can} Уровень пути {path_level}→{path_level+1} — {next_cost} 🔷",
            callback_data="craft_path_level"
        ))
    else:
        builder.row(InlineKeyboardButton(
            text="🔒 Уровень пути — выбери путь",
            callback_data="noop_raid"
        ))

    # Слияние путей
    if slots_full:
        builder.row(InlineKeyboardButton(
            text=f"🔒 Слияние путей — слот занят ({extra_count}/{slots})",
            callback_data="noop_raid"
        ))
    else:
        can_spin = "✅" if path_frags >= PATH_SPIN_CRAFT_COST else "❌"
        builder.row(InlineKeyboardButton(
            text=f"{can_spin} Слияние путей — {PATH_SPIN_CRAFT_COST} 🔷 ({extra_count}/{slots})",
            callback_data="craft_path_spin"
        ))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="raid_craft"))

    # Бонус уровня
    from app.utils.formatters import skill_path_label
    level_bonus_info = ""
    if user.skill_path:
        bonuses = PATH_LEVEL_BONUSES.get(user.skill_path, {})
        if bonuses:
            parts = [f"+{v} {k.replace('_', ' ')}" for k, v in bonuses.items()]
            level_bonus_info = f"\n<i>Бонус за уровень: {', '.join(parts)}</i>"

    next_cost_str = (
        f"{PATH_LEVEL_COSTS[path_level]} 🔷" if path_level < PATH_LEVEL_MAX else "МАКС"
    )
    spin_status = (
        f"🔒 слот занят ({extra_count}/{slots})" if slots_full
        else f"{path_frags}/{PATH_SPIN_CRAFT_COST} 🔷"
    )

    await cb.message.edit_text(
        f"🔷 <b>Крафт Пути</b>\n\n"
        f"🔷 Фрагменты Пути: <b>{path_frags}</b>\n\n"
        f"<b>── Уровень пути ──</b>\n"
        f"Текущий: <b>{path_level}/{PATH_LEVEL_MAX}</b>{level_bonus_info}\n"
        f"Следующий уровень: <b>{next_cost_str}</b>\n\n"
        f"<b>── Слияние путей ──</b>\n"
        f"Слоты: <b>{extra_count}/{slots}</b>\n"
        f"Стоимость прокрутки: <b>{spin_status}</b>\n"
        f"<i>Случайный навык из другого пути</i>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("raid_attack:"))
async def cb_raid_attack(cb: CallbackQuery, session: AsyncSession, user: User):
    raid_id = int(cb.data.split(":")[1])
    result = await raid_service.attack_boss(session, user, raid_id)

    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    if result.get("boss_killed"):
        rt = result.get("reward_type")
        if rt == "alchemy":
            frag_emoji, frag_name = "🧪", "фрагментов алхимии"
        elif rt == "path":
            frag_emoji, frag_name = "🔷", "фрагментов Пути"
        else:
            frag_emoji, frag_name = "🔮", "фрагментов УИ"
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

@router.callback_query(F.data == "craft_path_level")
async def cb_craft_path_level(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.services.skill_service import skill_service as _ss
    result = await _ss.upgrade_path_level(session, user)
    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    bonuses = result["bonuses"]
    bonus_str = ", ".join(f"+{v} {k.replace('_', ' ')}" for k, v in bonuses.items()) if bonuses else ""
    await cb.answer(
        f"⭐ Уровень пути повышен до {result['new_level']}!\n{bonus_str}",
        show_alert=True
    )
    await cb_craft_path_menu(cb, session, user)


@router.callback_query(F.data == "craft_path_spin")
async def cb_craft_path_spin(cb: CallbackQuery, session: AsyncSession, user: User):
    result = await raid_service.craft_path_spin(session, user)
    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    synergy = result.get("synergy")
    text = f"🔷 Получен навык: {result['emoji']} {result['skill']}!\n({result['description']})"
    if synergy:
        text += f"\n\n✨ Синергия активирована: {synergy['emoji']} {synergy['name']}!"
    await cb.answer(text, show_alert=True)
    await cb_craft_path_menu(cb, session, user)


@router.callback_query(F.data == "noop_raid")
async def cb_noop_raid(cb: CallbackQuery):
    await cb.answer()