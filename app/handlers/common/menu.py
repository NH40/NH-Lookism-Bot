import html

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.utils.keyboards.common import main_menu_kb, back_kb
from app.utils.formatters import fmt_num, phase_label
from ._common import _main_menu_text, _phase_emoji

router = Router()


# ── /start ──────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, user: User, is_new_user: bool):
    args = message.text.split()
    if is_new_user and len(args) > 1 and args[1].startswith("ref_"):
        try:
            teacher_tg_id = int(args[1].replace("ref_", ""))
            from app.services.referral_service import referral_service
            await referral_service.register_with_referral(session, user, teacher_tg_id)
            user.nh_coins += 2000
            await session.flush()
        except Exception:
            pass

    from app.services.title_service import title_service
    from app.data.titles import DONAT_SETS as _DS
    has_vvip = all([await title_service.has_set(session, user.id, s.set_id) for s in _DS])
    if is_new_user:
        await message.answer(
            f"👋 Добро пожаловать, <b>{html.escape(user.full_name)}</b>!\n\n"
            f"Ты начинаешь путь уличного бойца.\n"
            f"Цель — стать Императором!\n\n"
            f"🏴 Банда → 👑 Король → ✊ Кулак → 🏛 Император",
            reply_markup=main_menu_kb(has_vvip=has_vvip),
            parse_mode="HTML",
        )
    else:
        text = await _main_menu_text(session, user)
        await message.answer(text, reply_markup=main_menu_kb(has_vvip=has_vvip), parse_mode="HTML")


# ── Главное меню ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "main_menu")
async def cb_main_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    text = await _main_menu_text(session, user)
    from app.services.title_service import title_service
    from app.data.titles import DONAT_SETS as _DS
    has_vvip = all([await title_service.has_set(session, user.id, s.set_id) for s in _DS])
    kb = main_menu_kb(has_vvip=has_vvip)
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        # Текущее сообщение может быть фото (боссы, рейды и т.д.) — удаляем и отправляем текст
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()


# ── Профиль ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "profile")
async def cb_profile(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.repositories.title_repo import title_repo
    from app.repositories.city_repo import city_repo
    from app.services.business_service import business_service

    titles_str = await title_repo.get_titles_display(session, user.id)
    districts  = await city_repo.get_user_district_count(session, user.id)
    info       = await business_service.get_income_breakdown(session, user)

    prestige_str = ""
    if user.prestige_level > 0:
        prestige_str = (
            f"\n━━━ 🌟 Пробуждение ━━━\n"
            f"Уровень: {user.prestige_level}/10\n"
            f"  +{user.prestige_level * 5}% мощь | "
            f"+{user.prestige_income_bonus}% доход | "
            f"+{user.prestige_ticket_bonus}% тикет"
        )

    ui_str = ""
    if user.ui_level > 0 or user.ui_is_donat or user.ui_fragments > 0 or user.alchemy_fragments > 0:
        from app.handlers.skills.med_genius import any_unlocked, _unlocked_count, MG_POTIONS, is_donat as _mg_is_donat
        ui_level_label = "Донат (макс)" if user.ui_is_donat else f"Уровень {user.ui_level}/4"
        if _mg_is_donat(user):
            mg_label = " ✅ Донат (все Ур.6)"
        elif any_unlocked(user):
            mg_label = f" {_unlocked_count(user)}/{len(MG_POTIONS)} зелий"
        else:
            mg_label = " 🔒 не открыто"
        ui_str = (
            f"\n\n━━━ 👁 Ультра Инстинкт ━━━\n"
            f"{ui_level_label}\n"
            f"🔮 Фрагменты УИ: {user.ui_fragments}\n"
            f"🧪 Фрагменты алхимии: {user.alchemy_fragments}\n"
            f"🩺 Гений медицины:{mg_label}"
        )

    text = (
        f"📊 <b>Профиль</b>\n\n"
        f"👤 {html.escape(user.full_name)}"
        + (f"\n🏴 Банда: {html.escape(user.gang_name)}" if user.gang_name else "")
        + f"\n{_phase_emoji(user.phase)} {phase_label(user.phase)}"
        + (f" | 🌐 Сектор {user.sector}" if user.sector else "")
        + f"\n\n━━━ 💰 Финансы ━━━\n"
        f"NHCoin: {fmt_num(user.nh_coins)}\n"
        f"Доход: {fmt_num(info['base_income'])}/мин"
        + (f" → {fmt_num(info['final_income'])}/мин" if info['final_income'] != info['base_income'] else "")
        + (f" (+{info['total_bonus_percent']}%)" if info['total_bonus_percent'] else "")
        + (f"\n  💎 Клан-донат: +{info['clan_donat_income_bonus']}% к доходу" if info.get('clan_donat_income_bonus') else "")
        + (
            (
                f"\n  💸 Пассивный: +{fmt_num(info['circ_passive_per_min'])}/мин"
                + (
                    f" (🧪 +{info['potion_bonus']}%)"
                    if info.get('potion_bonus') and info['circ_passive_per_min'] != (info['circ_passive_income'] or 0)
                    else ""
                )
            )
            if info.get('circ_passive_income') else ""
        )
        + f"\n\n━━━ ⚔️ Боевые ━━━\n"
        f"Мощь: {fmt_num(user.combat_power)}\n"
        f"Влияние: {fmt_num(user.influence)}\n\n"
        f"━━━ 🏙 Территория ━━━\n"
        f"Районов: {districts} | Городов: {user.king_cities_count}"
        + prestige_str
        + ui_str
        + f"\n\n━━━ 💎 Титулы ━━━\n"
        + titles_str
    )
    await cb.message.edit_text(text, reply_markup=back_kb("settings"), parse_mode="HTML")
