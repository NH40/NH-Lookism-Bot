from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.raid_service import raid_service
from app.services.cooldown_service import cooldown_service
from app.services.quest_service import quest_service
from app.services.skill_service import skill_service as _ss
from app.constants.raid import (
    PATH_SPIN_CRAFT_COST,
    PATH_LEVEL_MAX,
    PATH_LEVEL_COSTS,
    PATH_LEVEL_BONUSES,
    UI_CRAFT_COST,
    UI_LEVEL_PERKS,
    BIZ_GENIUS_COSTS,
    BIZ_GENIUS_INCOME_BONUS,
    BIZ_GENIUS_LEVEL_LABELS,
    BUSINESS_DISTRICT_COST,
    BUSINESS_DISTRICTS_MAX,
)
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_num
from app.handlers.raid.boss import _raid_boss_photo, _send_or_edit_raid_photo

router = Router()


# ── Получение награды ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("raid_claim:"))
async def cb_raid_claim(cb: CallbackQuery, session: AsyncSession, user: User):
    raid_id = int(cb.data.split(":")[1])
    result = await raid_service.finish_raid(session, user, raid_id)

    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    await quest_service.add_progress(session, user, "raid_win")

    reward_type = result.get("reward_type")
    if reward_type == "alchemy":
        frag_emoji, frag_name = "🧪", "фрагментов алхимии"
    elif reward_type == "path":
        frag_emoji, frag_name = "🔷", "фрагментов Пути"
    elif reward_type == "business":
        frag_emoji, frag_name = "🏢", "бизнес-фрагментов"
    else:
        frag_emoji, frag_name = "🔮", "фрагментов УИ"

    doubled_line = "\n🌀 <b>Удача! Награда удвоена!</b>" if result.get("doubled") else ""
    claim_text = (
        f"🎉 <b>Рейд завершён!</b>\n\n"
        f"👹 Босс: {result['boss_name']}\n"
        f"💥 Нанесённый урон: <b>{fmt_num(result['damage'])}</b>\n\n"
        f"{frag_emoji} Получено {frag_name}: <b>+{result['fragments']}</b>\n"
        f"📊 Всего: <b>{result['total_fragments']}</b>"
        + doubled_line + "\n\n"
        f"Используй фрагменты в <b>Рейды → Крафт</b>!"
    )
    photo = _raid_boss_photo(result.get("boss_id", ""))
    await _send_or_edit_raid_photo(cb, photo, claim_text, back_kb("raid_menu"))


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


# ── Крафт Гений медицины — подменю ───────────────────────────────────────────

@router.callback_query(F.data == "craft_mg_menu")
async def cb_craft_mg_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.handlers.skills.med_genius import (
        MG_POTIONS, MG_LEVEL_COSTS, MG_BUY_MAX_LEVEL,
        is_donat as _mg_is_donat, potion_level,
    )
    from app.data.shop import MG_TIERS
    from app.utils.formatters import fmt_num

    donat = _mg_is_donat(user)
    frags = getattr(user, "alchemy_fragments", 0)

    builder = InlineKeyboardBuilder()
    lines = [
        "🩺 <b>Гений медицины — Крафт</b>",
        f"🧪 Фрагменты алхимии: <b>{frags}</b>",
        "<i>Фрагменты получаются у босса Джинен</i>",
        "",
        "<b>Зелья:</b>",
    ]

    if donat:
        lines.append("✨ <b>Донат активен</b> — все зелья на максимальном уровне (Ур.6)\n")
        for p in MG_POTIONS:
            tier = MG_TIERS[p["type"]][5]
            lines.append(f"  👑 {p['name']} [Ур.6] — +{tier.effect_value}%")
    else:
        for p in MG_POTIONS:
            lvl   = potion_level(user, p["type"])
            tiers = MG_TIERS[p["type"]]

            if lvl == 0:
                cost = MG_LEVEL_COSTS[0]
                mark = "✅" if frags >= cost else "❌"
                lines.append(f"🔒 {p['name']} — Ур.0 → <b>{cost} 🧪</b> {mark}")
                builder.row(InlineKeyboardButton(
                    text=f"{mark} {p['name']} Ур.1 — {cost} 🧪",
                    callback_data=f"craft_mg_buy:{p['type']}:1" if frags >= cost else "noop_raid",
                ))
            elif lvl < MG_BUY_MAX_LEVEL:
                cost      = MG_LEVEL_COSTS[lvl]
                next_tier = tiers[lvl]
                mark      = "✅" if frags >= cost else "❌"
                lines.append(
                    f"⬆️ {p['name']} [Ур.{lvl}] → Ур.{lvl+1}: "
                    f"<b>{cost} 🧪</b> {mark}"
                )
                builder.row(InlineKeyboardButton(
                    text=f"{mark} {p['name']} Ур.{lvl+1} — {cost} 🧪",
                    callback_data=f"craft_mg_buy:{p['type']}:{lvl+1}" if frags >= cost else "noop_raid",
                ))
            elif lvl == MG_BUY_MAX_LEVEL:
                lines.append(f"✅ {p['name']} [Ур.{lvl} макс] — Ур.6 только донат")
                builder.row(InlineKeyboardButton(
                    text=f"👑 {p['name']} Ур.6 — только донат",
                    callback_data="noop_raid",
                ))
            else:
                lines.append(f"✨ {p['name']} [Ур.{lvl}]")

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="raid_craft"))

    try:
        await cb.message.edit_text(
            "\n".join(lines),
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("craft_mg_buy:"))
async def cb_craft_mg_buy(cb: CallbackQuery, session: AsyncSession, user: User):
    parts = cb.data.split(":")
    potion_type  = parts[1]
    target_level = int(parts[2])

    result = await raid_service.craft_mg_level(session, user, potion_type, target_level)
    if not result["ok"]:
        await cb.answer(result["reason"], show_alert=True)
        return

    from app.handlers.skills.med_genius import MG_POTION_MAP
    name = MG_POTION_MAP.get(potion_type, {}).get("name", potion_type)
    await cb.answer(
        f"✅ {name} Ур.{result['new_level']} открыто!\n"
        f"+{result['effect']}% к эффекту\n"
        f"🧪 Осталось: {result['fragments_left']}",
        show_alert=True,
    )
    await cb_craft_mg_menu(cb, session, user)


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


# ── Гений бизнеса (Бизнес-крафт) ────────────────────────────────────────────

async def _biz_genius_page(cb: CallbackQuery, session: AsyncSession, user: User, back: str = "raid_craft"):
    """Общая функция отображения страницы Гения бизнеса."""
    biz_frags = getattr(user, "business_fragments", 0)
    biz_genius = getattr(user, "business_genius_level", 0)
    bonus_districts = getattr(user, "bonus_business_districts", 0)

    builder = InlineKeyboardBuilder()

    # ── Прокачка уровня Гения бизнеса ────────────────────────────────────────
    if biz_genius < 5:
        cost = BIZ_GENIUS_COSTS[biz_genius]
        can = "✅" if biz_frags >= cost else "❌"
        lbl = BIZ_GENIUS_LEVEL_LABELS.get(biz_genius + 1, "")
        builder.row(InlineKeyboardButton(
            text=f"{can} Ур.{biz_genius + 1}: {lbl} — {cost} 🏢",
            callback_data="biz_genius_upgrade"
        ))
    else:
        builder.row(InlineKeyboardButton(
            text="👑 Гений бизнеса — МАКСИМУМ (Ур.5)",
            callback_data="noop_raid"
        ))

    # ── Бизнес-экспансия: бонусные районы ────────────────────────────────────
    if bonus_districts < BUSINESS_DISTRICTS_MAX:
        can_d = "✅" if biz_frags >= BUSINESS_DISTRICT_COST else "❌"
        builder.row(InlineKeyboardButton(
            text=f"{can_d} +1 бонусный район — {BUSINESS_DISTRICT_COST} 🏢"
                 f" [{bonus_districts}/{BUSINESS_DISTRICTS_MAX}]",
            callback_data="craft_biz_district"
        ))
        if biz_frags >= BUSINESS_DISTRICT_COST * 5 and bonus_districts + 5 <= BUSINESS_DISTRICTS_MAX:
            builder.row(InlineKeyboardButton(
                text=f"✅ +5 районов — {BUSINESS_DISTRICT_COST * 5} 🏢",
                callback_data="craft_biz_district_5"
            ))
    else:
        builder.row(InlineKeyboardButton(
            text=f"✅ Бизнес-экспансия — максимум ({BUSINESS_DISTRICTS_MAX}/50)",
            callback_data="noop_raid"
        ))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=back))

    # ── Текст ─────────────────────────────────────────────────────────────────
    lines = [
        "🎖 <b>Гений бизнеса</b>",
        f"<i>Фрагменты — у Элиты (Нулевое поколение)</i>",
        "",
        f"🏢 Бизнес-фрагменты: <b>{biz_frags}</b>",
        f"🎖 Уровень: <b>{biz_genius}/5</b>",
        "",
        "<b>── Уровни Гения бизнеса ──</b>",
        "<i>Каждый уровень открывает новые здания и даёт бонус к доходу</i>",
        "",
    ]
    for lvl in range(1, 6):
        cost = BIZ_GENIUS_COSTS[lvl - 1]
        bonus = BIZ_GENIUS_INCOME_BONUS[lvl - 1]
        lbl = BIZ_GENIUS_LEVEL_LABELS.get(lvl, "")
        if biz_genius >= lvl:
            lines.append(f"✅ Ур.{lvl}: {lbl} — +{bonus}% доход")
        elif biz_genius + 1 == lvl:
            lines.append(f"🔓 Ур.{lvl}: {lbl} — {cost} 🏢 | +{bonus}% доход")
        else:
            lines.append(f"🔒 Ур.{lvl}: {lbl} — {cost} 🏢 | +{bonus}% доход")

    lines += [
        "",
        "<b>── Бизнес-экспансия ──</b>",
        f"<i>Бонусные районы для строительства без захвата городов</i>",
        f"🏘 Куплено: <b>{bonus_districts}/{BUSINESS_DISTRICTS_MAX}</b> | Цена: {BUSINESS_DISTRICT_COST} 🏢/р.",
    ]

    try:
        await cb.message.edit_text(
            "\n".join(lines),
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data == "craft_biz_menu")
async def cb_craft_biz_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    await _biz_genius_page(cb, session, user, back="raid_craft")


@router.callback_query(F.data == "biz_genius_menu")
async def cb_biz_genius_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    await _biz_genius_page(cb, session, user, back="business")


@router.callback_query(F.data == "biz_genius_upgrade")
async def cb_biz_genius_upgrade(cb: CallbackQuery, session: AsyncSession, user: User):
    biz_genius = getattr(user, "business_genius_level", 0)
    biz_frags = getattr(user, "business_fragments", 0)

    if biz_genius >= 5:
        await cb.answer("Максимальный уровень достигнут!", show_alert=True)
        return

    cost = BIZ_GENIUS_COSTS[biz_genius]
    if biz_frags < cost:
        await cb.answer(f"Нужно {cost} 🏢 фрагментов", show_alert=True)
        return

    user.business_fragments = biz_frags - cost
    user.business_genius_level = biz_genius + 1
    new_lvl = user.business_genius_level
    lbl = BIZ_GENIUS_LEVEL_LABELS.get(new_lvl, "")
    bonus = BIZ_GENIUS_INCOME_BONUS[new_lvl - 1]

    # Пересчитываем доход (добавился genius bonus)
    from app.services.business_service import business_service
    await business_service._recalc_income(session, user)
    await session.flush()

    await cb.answer(
        f"🎖 Гений бизнеса Ур.{new_lvl} открыт!\n"
        f"{lbl}\n"
        f"+{bonus}% ко всему доходу!\n"
        f"Новые здания доступны в Бизнесе!",
        show_alert=True
    )
    # Определяем куда вернуться (по тексту кнопки «Назад» в message нет надёжного способа,
    # поэтому всегда возвращаем в raid_craft; из бизнеса вызывается отдельный callback)
    await _biz_genius_page(cb, session, user, back="raid_craft")


@router.callback_query(F.data == "craft_biz_district")
async def cb_craft_biz_district(cb: CallbackQuery, session: AsyncSession, user: User):
    biz_frags = getattr(user, "business_fragments", 0)
    bonus_districts = getattr(user, "bonus_business_districts", 0)
    if bonus_districts >= BUSINESS_DISTRICTS_MAX:
        await cb.answer("Достигнут максимум бонусных районов!", show_alert=True)
        return
    if biz_frags < BUSINESS_DISTRICT_COST:
        await cb.answer(f"Нужно {BUSINESS_DISTRICT_COST} 🏢 фрагментов", show_alert=True)
        return
    user.business_fragments = biz_frags - BUSINESS_DISTRICT_COST
    user.bonus_business_districts = bonus_districts + 1
    await session.flush()
    await cb.answer(f"✅ +1 бонусный район! Всего: {user.bonus_business_districts}", show_alert=True)
    await _biz_genius_page(cb, session, user, back="raid_craft")


@router.callback_query(F.data == "craft_biz_district_5")
async def cb_craft_biz_district_5(cb: CallbackQuery, session: AsyncSession, user: User):
    cost5 = BUSINESS_DISTRICT_COST * 5
    biz_frags = getattr(user, "business_fragments", 0)
    bonus_districts = getattr(user, "bonus_business_districts", 0)
    if biz_frags < cost5:
        await cb.answer(f"Нужно {cost5} 🏢 фрагментов", show_alert=True)
        return
    add = min(5, BUSINESS_DISTRICTS_MAX - bonus_districts)
    if add <= 0:
        await cb.answer("Достигнут максимум!", show_alert=True)
        return
    user.business_fragments = biz_frags - (add * BUSINESS_DISTRICT_COST)
    user.bonus_business_districts = bonus_districts + add
    await session.flush()
    await cb.answer(f"✅ +{add} районов! Всего: {user.bonus_business_districts}", show_alert=True)
    await _biz_genius_page(cb, session, user, back="raid_craft")


# ── Обменник фрагментов (динамический) ───────────────────────────────────────
#
# Курс 1:1, стоимость 250 000 NHCoin за каждый обмениваемый фрагмент.

EXCHANGE_COST_PER_FRAG = 250_000

# type_key → (emoji, поле на User, отображаемое название)
EXCH_FRAGS: dict[str, tuple[str, str, str]] = {
    "ui":       ("🔮", "ui_fragments",       "Фрагменты УИ"),
    "alchemy":  ("🧪", "alchemy_fragments",  "Фрагменты алхимии"),
    "path":     ("🔷", "path_fragments",     "Фрагменты Пути"),
    "business": ("🏢", "business_fragments", "Фрагменты бизнеса"),
}


class FragExchangeFSM(StatesGroup):
    waiting_amount = State()


def _exch_menu_text(user: User) -> str:
    lines = [
        "💱 <b>Обменник фрагментов</b>",
        "<i>Курс 1:1 — стоимость 250 000 NHCoin за каждый фрагмент</i>",
        "",
    ]
    for key, (emoji, field, label) in EXCH_FRAGS.items():
        lines.append(f"{emoji} {label}: <b>{getattr(user, field, 0)}</b>")
    lines.append(f"💰 NHCoin: <b>{fmt_num(user.nh_coins)}</b>")
    lines.append("")
    lines.append("Выберите тип фрагментов <b>отдать</b>:")
    return "\n".join(lines)


@router.callback_query(F.data == "craft_exchange_menu")
async def cb_craft_exchange_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    builder = InlineKeyboardBuilder()
    for key, (emoji, field, label) in EXCH_FRAGS.items():
        balance = getattr(user, field, 0)
        builder.row(InlineKeyboardButton(
            text=f"{emoji} {label}: {balance}",
            callback_data=f"exch_from:{key}",
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="raid_craft"))
    try:
        await cb.message.edit_text(
            _exch_menu_text(user),
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("exch_from:"))
async def cb_exch_from(cb: CallbackQuery, session: AsyncSession, user: User):
    from_key = cb.data.split(":")[1]
    if from_key not in EXCH_FRAGS:
        await cb.answer("Неверный тип фрагмента", show_alert=True)
        return

    from_emoji, from_field, from_label = EXCH_FRAGS[from_key]
    balance = getattr(user, from_field, 0)

    builder = InlineKeyboardBuilder()
    for key, (emoji, field, label) in EXCH_FRAGS.items():
        if key == from_key:
            continue
        builder.row(InlineKeyboardButton(
            text=f"{emoji} {label}",
            callback_data=f"exch_to:{from_key}:{key}",
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="craft_exchange_menu"))
    try:
        await cb.message.edit_text(
            f"💱 <b>Обмен</b> {from_emoji} {from_label}\n"
            f"Ваш баланс: <b>{balance}</b>\n\n"
            f"Выберите тип фрагментов <b>получить</b>:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("exch_to:"))
async def cb_exch_to(cb: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    parts = cb.data.split(":")
    if len(parts) < 3:
        await cb.answer("Ошибка", show_alert=True)
        return
    from_key, to_key = parts[1], parts[2]
    if from_key not in EXCH_FRAGS or to_key not in EXCH_FRAGS or from_key == to_key:
        await cb.answer("Неверные типы фрагментов", show_alert=True)
        return

    from_emoji, from_field, from_label = EXCH_FRAGS[from_key]
    to_emoji, to_field, to_label = EXCH_FRAGS[to_key]
    balance = getattr(user, from_field, 0)

    await state.set_state(FragExchangeFSM.waiting_amount)
    await state.update_data(from_key=from_key, to_key=to_key)

    cancel_kb = InlineKeyboardBuilder()
    cancel_kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="craft_exchange_menu"))
    try:
        await cb.message.edit_text(
            f"💱 <b>Обмен</b>\n"
            f"{from_emoji} {from_label} → {to_emoji} {to_label}\n\n"
            f"Баланс: <b>{balance}</b> {from_emoji}\n"
            f"Курс: 1:1 | Цена: {fmt_num(EXCHANGE_COST_PER_FRAG)} NHCoin за фрагмент\n\n"
            f"Введите количество фрагментов для обмена:",
            reply_markup=cancel_kb.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.message(FragExchangeFSM.waiting_amount)
async def msg_exch_amount(message: Message, session: AsyncSession, user: User, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    from_key = data.get("from_key")
    to_key   = data.get("to_key")

    if not from_key or not to_key or from_key not in EXCH_FRAGS or to_key not in EXCH_FRAGS:
        await message.answer("❌ Ошибка сессии, начните обмен заново.", reply_markup=back_kb("craft_exchange_menu"), parse_mode="HTML")
        return

    try:
        amount = int(message.text.strip().replace(" ", "").replace(",", ""))
    except ValueError:
        await message.answer("❌ Введите целое число.", reply_markup=back_kb("craft_exchange_menu"), parse_mode="HTML")
        return

    if amount <= 0:
        await message.answer("❌ Количество должно быть > 0.", reply_markup=back_kb("craft_exchange_menu"), parse_mode="HTML")
        return

    from_emoji, from_field, from_label = EXCH_FRAGS[from_key]
    to_emoji,   to_field,   to_label   = EXCH_FRAGS[to_key]

    src_have = getattr(user, from_field, 0)
    coin_cost = amount * EXCHANGE_COST_PER_FRAG

    if src_have < amount:
        await message.answer(
            f"❌ Недостаточно {from_emoji} {from_label}.\n"
            f"Есть: {src_have}, нужно: {amount}",
            reply_markup=back_kb("craft_exchange_menu"),
            parse_mode="HTML",
        )
        return

    if user.nh_coins < coin_cost:
        await message.answer(
            f"❌ Недостаточно NHCoin.\n"
            f"Нужно: {fmt_num(coin_cost)}, есть: {fmt_num(user.nh_coins)}",
            reply_markup=back_kb("craft_exchange_menu"),
            parse_mode="HTML",
        )
        return

    setattr(user, from_field, src_have - amount)
    setattr(user, to_field,   getattr(user, to_field, 0) + amount)
    user.nh_coins -= coin_cost
    await session.flush()

    await message.answer(
        f"✅ <b>Обмен выполнен!</b>\n\n"
        f"Отдано: {amount} {from_emoji} {from_label}\n"
        f"Получено: {amount} {to_emoji} {to_label}\n"
        f"Стоимость: -{fmt_num(coin_cost)} NHCoin",
        reply_markup=back_kb("craft_exchange_menu"),
        parse_mode="HTML",
    )
