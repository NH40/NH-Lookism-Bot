"""
Гений медицины — тировая система авто-зелий.

Уровни 1–5 каждого зелья открываются за фрагменты алхимии.
Уровень 6 — только через донат (Сет УИ, «Гений медицины (Фулл)»).

Каждый уровень = более сильное и дорогое зелье (отдельный тир).
Авто-покупка: при отсутствии активного зелья и наличии монет —
  покупает тир, соответствующий текущему уровню данного зелья.

Стоимость крафта (фрагменты алхимии — одинакова для всех типов):
  Ур.1 → 30   Ур.2 → 80   Ур.3 → 200
  Ур.4 → 500  Ур.5 → 1200  Ур.6 — только донат
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.utils.formatters import fmt_num

router = Router()

MG_MAX_LEVEL     = 6   # 6-й уровень только через донат
MG_BUY_MAX_LEVEL = 5   # максимальный уровень за фрагменты

# Стоимость крафта уровней 1–5 (индекс 0 = уровень 1)
MG_LEVEL_COSTS: list[int] = [30, 80, 200, 500, 1_200]

# Все типы зелий МГ
MG_POTIONS: list[dict] = [
    {
        "type":         "power",
        "name":         "⚔️ Зелье силы",
        "level_field":  "mg_level_power",
        "toggle_field": "mg_auto_power",
    },
    {
        "type":         "training",
        "name":         "🏋 Зелье тренировки",
        "level_field":  "mg_level_training",
        "toggle_field": "mg_auto_training",
    },
    {
        "type":         "income",
        "name":         "💰 Зелье богатства",
        "level_field":  "mg_level_income",
        "toggle_field": "mg_auto_income",
    },
    {
        "type":         "luck",
        "name":         "🍀 Зелье удачи",
        "level_field":  "mg_level_luck",
        "toggle_field": "mg_auto_luck",
    },
    {
        "type":         "influence",
        "name":         "⚡ Зелье влияния",
        "level_field":  "mg_level_influence",
        "toggle_field": "mg_auto_influence",
    },
    {
        "type":         "raid_drop",
        "name":         "💠 Зелье охотника",
        "level_field":  "mg_level_raid_drop",
        "toggle_field": "mg_auto_raid_drop",
    },
]
MG_POTION_MAP: dict[str, dict] = {p["type"]: p for p in MG_POTIONS}


def is_donat(user: User) -> bool:
    return bool(getattr(user, "med_genius_donat", False))


def potion_level(user: User, potion_type: str) -> int:
    """Текущий уровень зелья (6 если донат)."""
    cfg = MG_POTION_MAP.get(potion_type)
    if not cfg:
        return 0
    if is_donat(user):
        return MG_MAX_LEVEL
    return getattr(user, cfg["level_field"], 0)


def mg_level(user: User) -> int:
    """Уровень Зелья силы (для совместимости с menu.py, profile)."""
    return potion_level(user, "power")


def any_unlocked(user: User) -> bool:
    if is_donat(user):
        return True
    return any(getattr(user, p["level_field"], 0) > 0 for p in MG_POTIONS)


def _unlocked_count(user: User) -> int:
    if is_donat(user):
        return len(MG_POTIONS)
    return sum(1 for p in MG_POTIONS if getattr(user, p["level_field"], 0) > 0)


# ── Главный экран ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "med_genius")
async def cb_med_genius(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.data.shop import MG_TIERS

    donat    = is_donat(user)
    unlocked = _unlocked_count(user)

    lines = ["🩺 <b>Гений медицины</b>\n"]
    if donat:
        lines.append("✨ <b>Донат активен</b> — все зелья на максимальном уровне (Ур.6)\n")
    else:
        lines.append(f"📊 Открыто зелий: <b>{unlocked}/{len(MG_POTIONS)}</b>")
        lines.append(f"<i>Открыть уровни: Рейды → Крафт → Гений медицины</i>\n")

    lines.append("<b>Авто-зелья:</b>")
    has_any = False
    for p in MG_POTIONS:
        lvl = potion_level(user, p["type"])
        if lvl == 0:
            lines.append(f"  🔒 {p['name']} — не открыто")
        else:
            has_any = True
            enabled = getattr(user, p["toggle_field"], True)
            status  = "✅" if enabled else "❌"
            tier    = MG_TIERS[p["type"]][lvl - 1]
            lines.append(
                f"  {status} {p['name']} [Ур.{lvl}] — "
                f"+{tier.effect_value}% | {fmt_num(tier.price)} монет"
            )

    builder = InlineKeyboardBuilder()
    if has_any or donat:
        builder.row(InlineKeyboardButton(
            text="⚙️ Вкл/Выкл авто-зелий",
            callback_data="mg_toggles",
        ))
    if not donat:
        builder.row(InlineKeyboardButton(
            text="🔨 Открыть уровни (Крафт)",
            callback_data="craft_mg_menu",
        ))
    builder.row(InlineKeyboardButton(text="◀️ Навыки", callback_data="skills"))

    try:
        await cb.message.edit_text(
            "\n".join(lines),
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


# ── Настройки переключателей ──────────────────────────────────────────────────

@router.callback_query(F.data == "mg_toggles")
async def cb_mg_toggles(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.data.shop import MG_TIERS

    if not any_unlocked(user):
        await cb.answer("Сначала откройте хотя бы одно зелье", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    lines = [
        "⚙️ <b>Авто-зелья — настройки</b>\n",
        "Нажмите на зелье чтобы включить/выключить авто-покупку:\n",
    ]

    for p in MG_POTIONS:
        lvl = potion_level(user, p["type"])
        if lvl == 0:
            continue
        enabled = getattr(user, p["toggle_field"], True)
        status  = "✅" if enabled else "❌"
        tier    = MG_TIERS[p["type"]][lvl - 1]
        lines.append(
            f"  {status} {p['name']} [Ур.{lvl}] "
            f"+{tier.effect_value}% | {fmt_num(tier.price)}"
        )
        builder.row(InlineKeyboardButton(
            text=f"{status} {p['name']}",
            callback_data=f"mg_toggle:{p['type']}",
        ))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="med_genius"))

    try:
        await cb.message.edit_text(
            "\n".join(lines),
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("mg_toggle:"))
async def cb_mg_toggle(cb: CallbackQuery, session: AsyncSession, user: User):
    potion_type = cb.data.split(":")[1]
    cfg = MG_POTION_MAP.get(potion_type)
    if not cfg or not hasattr(user, cfg["toggle_field"]):
        await cb.answer("Неизвестный тип зелья", show_alert=True)
        return
    current = getattr(user, cfg["toggle_field"], True)
    setattr(user, cfg["toggle_field"], not current)
    await session.commit()
    state = "включено ✅" if not current else "выключено ❌"
    await cb.answer(f"{cfg['name']}: {state}")
    await cb_mg_toggles(cb, session, user)


# Устаревший тоггл (для обратной совместимости)
@router.callback_query(F.data == "mg_toggle_power")
async def cb_mg_toggle_power(cb: CallbackQuery, session: AsyncSession, user: User):
    cb.data = "mg_toggle:power"
    await cb_mg_toggle(cb, session, user)
