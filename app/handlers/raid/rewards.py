from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.raid_service import raid_service
from app.services.cooldown_service import cooldown_service
from app.services.skill_service import skill_service as _ss
from app.constants.raid import (
    ALCHEMY_CRAFT_COST,
    PATH_SPIN_CRAFT_COST,
    PATH_LEVEL_MAX,
    PATH_LEVEL_COSTS,
    PATH_LEVEL_BONUSES,
    UI_CRAFT_COST,
    UI_LEVEL_PERKS,
)
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_num

router = Router()


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
    path_frags = getattr(user, "path_fragments", 0)
    path_level = getattr(user, "skill_path_level", 0)
    slots = getattr(user, "extra_path_skill_slots", 1)
    extra_count = await _ss.get_extra_path_skills_count(session, user) if user.skill_path else 0
    slots_full = extra_count >= slots

    builder = InlineKeyboardBuilder()

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


@router.callback_query(F.data == "craft_path_level")
async def cb_craft_path_level(cb: CallbackQuery, session: AsyncSession, user: User):
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
