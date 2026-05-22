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

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🏗 Построить здание", callback_data="biz_build"
    ))
    builder.row(InlineKeyboardButton(
        text="🏢 Мои здания", callback_data="biz_my_buildings"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Главное меню", callback_data="main_menu"
    ))

    bonuses = []
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

    try:
        await cb.message.edit_text(
            f"🏢 <b>Бизнес</b>\n\n"
            f"📍 Путь: {path_info.get('color','')} "
            f"{path_info.get('emoji','')} {path_info.get('name','')}"
            f"{influence_note}\n"
            f"{'─'*22}\n"
            f"💰 Базовый доход: {fmt_num(info['base_income'])}/мин\n"
            f"📈 Итого: {fmt_num(info['final_income'])}/мин"
            + bonus_str,
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
