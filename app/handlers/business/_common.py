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
        "desc": "Стабильный доход, влияние не меняется",
        "color": "🟢",
    },
    "illegal": {
        "name": "Нелегальный",
        "emoji": "🕶",
        "desc": "−Влияние при постройке, +влияние при сносе. Лучший доход",
        "color": "🔴",
    },
    "political": {
        "name": "Политика",
        "emoji": "🏛",
        "desc": "+Влияние при постройке, −влияние при сносе",
        "color": "🔵",
    },
    "digital": {
        "name": "Цифровой",
        "emoji": "💻",
        "desc": "Дешёвые районы + Сетевой эффект: +10% доход за каждые 10 зданий (макс +50%)",
        "color": "🟣",
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

    # Бонусы к доходу
    bonuses = []
    if info.get('network_bonus'):
        bonuses.append(f"  🌐 Сетевой эффект: +{info['network_bonus']}%")
    if info.get('biz_genius_bonus'):
        bonuses.append(f"  🎖 Гений бизнеса: +{info['biz_genius_bonus']}%")
    if info.get('skills_bonus'):
        bonuses.append(f"  📊 Навыки / Титул: +{info['skills_bonus']}%")
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

    bonus_section = ""
    if bonuses:
        bonus_section = "\n\n<b>Бонусы к доходу:</b>\n" + "\n".join(bonuses)

    # Влияние пути
    influence_note = ""
    if user.business_path == "illegal":
        influence_note = "  <i>⚠️ −влияние за постройку</i>\n"
    elif user.business_path == "political":
        influence_note = "  <i>✅ +влияние за постройку</i>\n"

    # Пассивный доход от циркуляции
    circ_line = ""
    circ_passive = info.get("circ_passive_income", 0)
    if circ_passive:
        circ_per_min = info.get("circ_passive_per_min", 0) or circ_passive
        circ_line = f"\n💸 Пассивный доход: +{fmt_num(circ_per_min)}/мин"

    from app.constants.raid import BIZ_GENIUS_LEVEL_LABELS, BIZ_GENIUS_DISCOUNT, BIZ_GENIUS_INCOME_BONUS
    genius_label = BIZ_GENIUS_LEVEL_LABELS.get(biz_genius, "") if biz_genius > 0 else "не открыт"
    genius_discount = BIZ_GENIUS_DISCOUNT[biz_genius - 1] if biz_genius > 0 else 0
    genius_income_b = BIZ_GENIUS_INCOME_BONUS[biz_genius - 1] if biz_genius > 0 else 0
    genius_perks = []
    if genius_income_b:
        genius_perks.append(f"+{genius_income_b}% доход")
    if genius_discount:
        genius_perks.append(f"-{genius_discount}% стройка")
    genius_perks_str = f" ({', '.join(genius_perks)})" if genius_perks else ""
    genius_str = f"Ур.{biz_genius}/5" + (f" — {genius_label}" if genius_label else "") + genius_perks_str

    # Дополнительная информация
    extra_lines = []
    if bonus_districts:
        extra_lines.append(f"🏘 Бонусных районов: <b>{bonus_districts}/50</b>")
    if biz_frags:
        extra_lines.append(f"🧩 Фрагментов: <b>{biz_frags}</b>")
    extra_section = ("\n" + "  ".join(extra_lines)) if extra_lines else ""

    text = (
        f"🏢 <b>Бизнес</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 {path_info.get('color','')} {path_info.get('emoji','')} <b>{path_info.get('name','')}</b>\n"
        f"{influence_note}"
        f"🎖 Гений бизнеса: <b>{genius_str}</b>"
        f"{extra_section}\n\n"
        f"💰 Базовый доход:  <b>{fmt_num(info['base_income'])}/мин</b>\n"
        f"📈 Итоговый доход: <b>{fmt_num(info['final_income'])}/мин</b>"
        f"{bonus_section}"
        f"{circ_line}"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏗 Построить",    callback_data="biz_build"),
        InlineKeyboardButton(text="🏢 Мои здания",   callback_data="biz_my_buildings"),
    )
    builder.row(InlineKeyboardButton(
        text=f"🎖 Гений бизнеса  [Ур.{biz_genius}/5]", callback_data="biz_genius_menu"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu"))

    try:
        await cb.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        pass
