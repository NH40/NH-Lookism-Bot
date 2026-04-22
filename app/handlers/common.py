from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.utils.keyboards.common import main_menu_kb, back_kb
from app.utils.formatters import fmt_num, fmt_power, phase_label, phase_emoji

router = Router()


def _phase_emoji(phase: str) -> str:
    return {
        "gang":    "🏴",
        "king":    "👑",
        "fist":    "✊",
        "emperor": "🏛",
    }.get(phase, "🏴")


def _main_menu_text(user: User) -> str:
    phase_str = f"{_phase_emoji(user.phase)} Фаза: {phase_label(user.phase)}"
    return (
        f"👤 {user.full_name}\n"
        f"{'🏴 Банда: ' + user.gang_name if user.gang_name else ''}\n"
        f"{'─' * 20}\n"
        f"📍 {phase_str}\n"
        f"💰 NHCoin: {fmt_num(user.nh_coins)}\n"
        f"⚡ Влияние: {fmt_num(user.influence)}\n"
        f"💪 Боевая мощь: {fmt_num(user.combat_power)}\n\n"
        f"Выбери раздел:"
    )


@router.message(CommandStart())
async def cmd_start(
    message: Message, session: AsyncSession,
    user: User, is_new_user: bool
):
    # Реферальная ссылка
    args = message.text.split()
    if is_new_user and len(args) > 1 and args[1].startswith("ref_"):
        try:
            teacher_tg_id = int(args[1].replace("ref_", ""))
            from app.services.referral_service import referral_service
            await referral_service.register_with_referral(
                session, user, teacher_tg_id
            )
            # Бонус новому игроку
            user.nh_coins += 2000
            await session.flush()
        except Exception:
            pass

    if is_new_user:
        await message.answer(
            f"👋 Добро пожаловать, <b>{user.full_name}</b>!\n\n"
            f"Ты начинаешь путь уличного бойца.\n"
            f"Цель — стать Императором!\n\n"
            f"🏴 Банда → 👑 Король → ✊ Кулак → 🏛 Император",
            reply_markup=main_menu_kb(),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            _main_menu_text(user),
            reply_markup=main_menu_kb(),
            parse_mode="HTML",
        )


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    try:
        await cb.message.edit_text(
            _main_menu_text(user),
            reply_markup=main_menu_kb(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data == "profile")
async def cb_profile(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.repositories.title_repo import title_repo
    from app.repositories.city_repo import city_repo
    from app.services.business_service import business_service
    from app.services.potion_service import potion_service

    titles_str = await title_repo.get_titles_display(session, user.id)
    districts = await city_repo.get_user_district_count(session, user.id)
    info = await business_service.get_income_breakdown(session, user)
    potions_str = await potion_service.get_active_summary(session, user.id)

    prestige_str = ""
    if user.prestige_level > 0:
        prestige_str = (
            f"\n━━━ 🌟 Пробуждение ━━━\n"
            f"Уровень: {user.prestige_level}/10\n"
            f"  +{user.prestige_level*5}% мощь | "
            f"+{user.prestige_income_bonus}% доход | "
            f"+{user.prestige_ticket_bonus}% тикет"
        )

    text = (
        f"📊 <b>Профиль</b>\n\n"
        f"👤 {user.full_name}"
        + (f"\n🏴 Банда: {user.gang_name}" if user.gang_name else "")
        + f"\n{_phase_emoji(user.phase)} {phase_label(user.phase)}"
        + (f" | 🌐 Сектор {user.sector}" if user.sector else "")
        + f"\n\n━━━ 💰 Финансы ━━━\n"
        f"NHCoin: {fmt_num(user.nh_coins)}\n"
        f"Доход: {fmt_num(info['base_income'])}/мин"
        + (f" → {fmt_num(info['final_income'])}/мин" if info['final_income'] != info['base_income'] else "")
        + f"\n\n━━━ ⚔️ Боевые ━━━\n"
        f"Мощь: {fmt_num(user.combat_power)}\n"
        f"Влияние: {fmt_num(user.influence)}\n\n"
        f"━━━ 🏙 Территория ━━━\n"
        f"Районов: {districts} | Городов: {user.king_cities_count}"
        + prestige_str
        + f"\n\n━━━ 💎 Титулы ━━━\n"
        + titles_str
        + (f"\n\n🧪 Зелья:\n{potions_str}" if potions_str else "")
    )
    await cb.message.edit_text(
        text,
        reply_markup=back_kb("settings"),
        parse_mode="HTML",
    )


@router.message(Command("players"))
async def cmd_players(message: Message, session: AsyncSession, user: User):
    from app.repositories.user_repo import user_repo
    top = await user_repo.get_top_by_power(session, 10)
    my_rank = await user_repo.get_rank_by_power(session, user.id)

    lines = ["🏆 <b>Топ-10 игроков</b>\n"]
    medals = {0: "🥇", 1: "🥈", 2: "🥉"}
    for i, u in enumerate(top):
        medal = medals.get(i, f"{i+1}.")
        vvip = " 👑" if u.ultra_instinct else ""
        lines.append(
            f"{medal} <b>{u.full_name}</b>{vvip}\n"
            f"   💪 {fmt_num(u.combat_power)} | {_phase_emoji(u.phase)} {phase_label(u.phase)}"
        )
    lines.append(f"\n📍 Твоё место: #{my_rank}")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession, user: User):
    from app.config import settings
    if message.from_user.id not in settings.admin_ids_list:
        return
    from app.utils.keyboards.admin import admin_main_kb
    await message.answer(
        "🔧 <b>Панель администратора</b>",
        reply_markup=admin_main_kb(),
        parse_mode="HTML",
    )