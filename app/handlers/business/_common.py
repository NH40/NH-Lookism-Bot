from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.services.business_service import business_service
from app.utils.formatters import fmt_num

PATH_INFO = {
    "legal": {
        "name": "Легальный",
        "emoji": "⚖️",
        "desc": "Стабильный доход, не влияет на влияние",
        "color": "🟢",
    },
    "illegal": {
        "name": "Нелегальный",
        "emoji": "🕶",
        "desc": "−Влияние при постройке, но больше дохода",
        "color": "🔴",
    },
    "political": {
        "name": "Политика",
        "emoji": "🏛",
        "desc": "+Влияние при постройке",
        "color": "🔵",
    },
}


async def _show_business_main(
    cb: CallbackQuery, session: AsyncSession, user: User
) -> None:
    info = await business_service.get_income_breakdown(session, user)
    path_info = PATH_INFO.get(user.business_path, {})

    biz_genius = getattr(user, "business_genius_level", 0)
    biz_frags = getattr(user, "business_fragments", 0)
    bonus_districts = getattr(user, "bonus_business_districts", 0)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🏗 Построить здание", callback_data="biz_build"
    ))
    builder.row(InlineKeyboardButton(
        text="🏢 Мои здания", callback_data="biz_my_buildings"
    ))
    builder.row(InlineKeyboardButton(
        text=f"🎖 Гений бизнеса [Ур.{biz_genius}/5]", callback_data="biz_genius_menu"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Главное меню", callback_data="main_menu"
    ))

    bonuses = []
    if info.get('biz_genius_bonus'):
        bonuses.append(f"  🎖 Гений бизнеса: +{info['biz_genius_bonus']}%")
    if info.get('skills_bonus'):
        bonuses.append(f"  📊 Навыки/Титул: +{info['skills_bonus']}%")
    if info['prestige_bonus']:
        bonuses.append(f"  🌟 Пробуждение: +{info['prestige_bonus']}%")
    if info['potion_bonus']:
        bonuses.append(f"  🧪 Зелье: +{info['potion_bonus']}%")
    if info.get('clan_income_bonus'):
        bonuses.append(f"  🏯 Клан: +{info['clan_income_bonus']}%")
    if info.get('clan_donat_income_bonus'):
        bonuses.append(f"  💎 Клан-донат: +{info['clan_donat_income_bonus']}%")
    if info['district_multiplier'] != 1.0:
        bonuses.append(f"  ×{info['district_multiplier']:.1f} мультипликатор")
    bonus_str = ("\n" + "\n".join(bonuses)) if bonuses else ""

    influence_note = ""
    if user.business_path == "illegal":
        influence_note = "\n⚠️ Нелегальный путь: −влияние за постройку"
    elif user.business_path == "political":
        influence_note = "\n✅ Политика: +влияние за постройку"

    circ_passive = info.get("circ_passive_income", 0)
    circ_line = ""
    if circ_passive:
        circ_per_min  = info.get("circ_passive_per_min", 0)
        total_bonus   = info.get("total_bonus_percent", 0)
        potion_bonus  = info.get("potion_bonus", 0)
        circ_all_pct  = total_bonus + potion_bonus
        base_per_min  = circ_passive  # уже в NHCoin/мин
        if circ_all_pct and circ_per_min != base_per_min:
            circ_line = (
                f"\n💸 Пассивный доход: +{fmt_num(circ_per_min)}/мин"
                f" (с баффами +{circ_all_pct}%, базово {fmt_num(base_per_min)}/мин)"
            )
        else:
            circ_line = f"\n💸 Пассивный доход: +{fmt_num(circ_per_min or base_per_min)}/мин"

    from app.constants.raid import BIZ_GENIUS_LEVEL_LABELS
    genius_label = BIZ_GENIUS_LEVEL_LABELS.get(biz_genius, "Базовый уровень") if biz_genius > 0 else "🔒 Не открыт"
    genius_line = f"🎖 Гений бизнеса: <b>Ур.{biz_genius}/5</b> — {genius_label}"
    expansion_line = f"🏘 Бонусных районов: <b>{bonus_districts}/50</b>" if bonus_districts else ""
    frags_line = f"🏢 Бизнес-фрагменты: <b>{biz_frags}</b>"

    try:
        await cb.message.edit_text(
            f"🏢 <b>Бизнес</b>\n\n"
            f"📍 Путь: {path_info.get('color','')} "
            f"{path_info.get('emoji','')} {path_info.get('name','')}"
            f"{influence_note}\n"
            f"{genius_line}\n"
            + (expansion_line + "\n" if expansion_line else "")
            + f"{frags_line}\n"
            f"{'─'*22}\n"
            f"💰 Базовый доход: {fmt_num(info['base_income'])}/мин\n"
            f"📈 Итого: {fmt_num(info['final_income'])}/мин"
            + bonus_str
            + circ_line,
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
