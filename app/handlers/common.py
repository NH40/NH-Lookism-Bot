from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import CommandStart, Command
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.utils.keyboards.common import main_menu_kb, back_kb
from app.utils.formatters import fmt_num, fmt_power, phase_label

router = Router()

PAGE_SIZE = 10


def _phase_emoji(phase: str) -> str:
    return {
        "gang":    "🏴",
        "king":    "👑",
        "fist":    "✊",
        "emperor": "🏛",
    }.get(phase, "🏴")


async def _main_menu_text(session: AsyncSession, user: User) -> str:
    from app.models.skill import UserMastery
    from app.services.potion_service import potion_service
    from datetime import datetime, timezone

    r = await session.execute(
        select(UserMastery).where(UserMastery.user_id == user.id)
    )
    mastery = r.scalar_one_or_none()

    bonus_map = {0: 0, 1: 5,  2: 10, 3: 20, 4: 30}
    speed_map = {0: 0, 1: 5,  2: 10, 3: 15, 4: 20}

    mastery_lines = []
    if mastery:
        if mastery.strength > 0:
            mastery_lines.append(
                f"  💪 Сила {mastery.strength}/4 (+{bonus_map[mastery.strength]}% мощи)"
            )
        if mastery.speed > 0:
            mastery_lines.append(
                f"  ⚡ Скорость {mastery.speed}/4 (-{speed_map[mastery.speed]}% КД)"
            )
        if mastery.endurance > 0:
            mastery_lines.append(
                f"  🛡 Выносливость {mastery.endurance}/4 (+{speed_map[mastery.endurance]}% порог)"
            )
        if mastery.technique > 0:
            mastery_lines.append(
                f"  🏋 Техника {mastery.technique}/4 (+{bonus_map[mastery.technique]}% трен./доход)"
            )

    path_emoji = {"businessman": "💼", "romantic": "💝", "monster": "👹"}
    path_name  = {"businessman": "Бизнесмен", "romantic": "Романтик", "monster": "Монстр"}
    path_line = ""
    if user.skill_path:
        emoji = path_emoji.get(user.skill_path, "🛤")
        name  = path_name.get(user.skill_path, user.skill_path)
        path_line = f"  {emoji} Путь: {name}"

    potions = await potion_service.get_active(session, user.id)
    now = datetime.now(timezone.utc)
    potion_lines = []
    potion_emoji_map = {
        "power": "⚔️", "wealth": "💰",
        "influence": "⚡", "training": "🏋", "luck": "🍀",
    }
    potion_name_map = {
        "power": "Сила", "wealth": "Богатство",
        "influence": "Влияние", "training": "Тренировка", "luck": "Удача",
    }
    for p in potions:
        remaining = max(0, int((p.expires_at - now).total_seconds()))
        m, s = divmod(remaining, 60)
        time_str = f"{m}м {s}с" if m else f"{s}с"
        emoji = potion_emoji_map.get(p.potion_type, "🧪")
        name  = potion_name_map.get(p.potion_type, p.potion_type)
        potion_lines.append(f"  {emoji} {name} +{p.bonus_value}% ({time_str})")

    ui_line = ""
    if user.ultra_instinct or user.true_ultra_instinct:
        tui = " TUI" if user.true_ultra_instinct else ""
        ui_line = f"  🤖 УИ{tui} активен"

    buff_lines = []
    if mastery_lines:
        buff_lines.append("━━━ ⚔️ Мастерство ━━━")
        buff_lines.extend(mastery_lines)
    if path_line or ui_line:
        buff_lines.append("━━━ 🛤 Развитие ━━━")
        if path_line:
            buff_lines.append(path_line)
        if ui_line:
            buff_lines.append(ui_line)
    if potion_lines:
        buff_lines.append("━━━ 🧪 Активные зелья ━━━")
        buff_lines.extend(potion_lines)

    buff_section = ("\n" + "\n".join(buff_lines)) if buff_lines else ""

    return (
        f"👤 {user.full_name}\n"
        + (f"🏴 Банда: {user.gang_name}\n" if user.gang_name else "")
        + f"{'─' * 20}\n"
        f"{_phase_emoji(user.phase)} Фаза: {phase_label(user.phase)}\n"
        f"💰 NHCoin: {fmt_num(user.nh_coins)}\n"
        f"⚡ Влияние: {fmt_num(user.influence)}\n"
        f"💪 Боевая мощь: {fmt_num(user.combat_power)}"
        + buff_section
        + "\n\nВыбери раздел:"
    )


# ── /start ──────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(
    message: Message, session: AsyncSession,
    user: User, is_new_user: bool
):
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
        text = await _main_menu_text(session, user)
        await message.answer(
            text,
            reply_markup=main_menu_kb(),
            parse_mode="HTML",
        )


# ── Главное меню ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "main_menu")
async def cb_main_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    text = await _main_menu_text(session, user)
    try:
        await cb.message.edit_text(
            text,
            reply_markup=main_menu_kb(),
            parse_mode="HTML",
        )
    except Exception:
        pass
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

    text = (
        f"📊 <b>Профиль</b>\n\n"
        f"👤 {user.full_name}"
        + (f"\n🏴 Банда: {user.gang_name}" if user.gang_name else "")
        + f"\n{_phase_emoji(user.phase)} {phase_label(user.phase)}"
        + (f" | 🌐 Сектор {user.sector}" if user.sector else "")
        + f"\n\n━━━ 💰 Финансы ━━━\n"
        f"NHCoin: {fmt_num(user.nh_coins)}\n"
        f"Доход: {fmt_num(info['base_income'])}/мин"
        + (
            f" → {fmt_num(info['final_income'])}/мин"
            if info['final_income'] != info['base_income'] else ""
        )
        + (f" (+{info['total_bonus_percent']}%)" if info['total_bonus_percent'] else "")
        + f"\n\n━━━ ⚔️ Боевые ━━━\n"
        f"Мощь: {fmt_num(user.combat_power)}\n"
        f"Влияние: {fmt_num(user.influence)}\n\n"
        f"━━━ 🏙 Территория ━━━\n"
        f"Районов: {districts} | Городов: {user.king_cities_count}"
        + prestige_str
        + f"\n\n━━━ 💎 Титулы ━━━\n"
        + titles_str
    )
    await cb.message.edit_text(
        text,
        reply_markup=back_kb("settings"),
        parse_mode="HTML",
    )


# ── /top ─────────────────────────────────────────────────────────────────────

@router.message(Command("top"))
async def cmd_top(message: Message, session: AsyncSession, user: User):
    from app.repositories.user_repo import user_repo
    top     = await user_repo.get_top_by_power(session, 10)
    my_rank = await user_repo.get_rank_by_power(session, user.id)

    lines  = ["🏆 <b>Топ-10 игроков по боевой мощи</b>\n"]
    medals = {0: "🥇", 1: "🥈", 2: "🥉"}
    for i, u in enumerate(top):
        medal = medals.get(i, f"{i + 1}.")
        vvip  = " 👑" if u.ultra_instinct else ""
        lines.append(
            f"{medal} <b>{u.full_name}</b>{vvip}\n"
            f"   💪 {fmt_num(u.combat_power)} | "
            f"{_phase_emoji(u.phase)} {phase_label(u.phase)}"
        )
    lines.append(f"\n📍 Твоё место: #{my_rank}")

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="👥 Все игроки", callback_data="players_page:0"
    ))
    await message.answer(
        "\n".join(lines),
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


# ── /players ─────────────────────────────────────────────────────────────────

@router.message(Command("players"))
async def cmd_players(message: Message, session: AsyncSession, user: User):
    await _show_players_page(message, session, user, page=0, edit=False)


async def _show_players_page(
    message, session: AsyncSession, user: User,
    page: int, edit: bool = True
) -> None:
    from app.models.user import User as UserModel

    total = await session.scalar(
        select(func.count(UserModel.id))
    ) or 0
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    result = await session.execute(
        select(UserModel)
        .order_by(UserModel.combat_power.desc())
        .offset(page * PAGE_SIZE)
        .limit(PAGE_SIZE)
    )
    players = result.scalars().all()

    start_rank = page * PAGE_SIZE + 1
    lines = [
        f"👥 <b>Все игроки</b> "
        f"(стр. {page + 1}/{total_pages}, всего {total})\n"
    ]
    for i, p in enumerate(players):
        rank_num = start_rank + i
        is_me    = " ← ты" if p.id == user.id else ""
        vvip     = " 👑" if p.ultra_instinct else ""
        lines.append(
            f"<b>#{rank_num}</b> {p.full_name}{vvip}{is_me}\n"
            f"  {_phase_emoji(p.phase)} {phase_label(p.phase)} | "
            f"💪 {fmt_num(p.combat_power)}"
        )

    text = "\n".join(lines)

    # Навигация
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text="◀️", callback_data=f"players_page:{page - 1}"
        ))
    nav.append(InlineKeyboardButton(
        text=f"{page + 1}/{total_pages}",
        callback_data="noop_players"
    ))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(
            text="▶️", callback_data=f"players_page:{page + 1}"
        ))

    builder = InlineKeyboardBuilder()
    builder.row(*nav)
    builder.row(InlineKeyboardButton(
        text="🏆 Топ-10", callback_data="show_top"
    ))

    if edit:
        try:
            await message.edit_text(
                text,
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
            )
        except Exception:
            pass
    else:
        await message.answer(
            text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("players_page:"))
async def cb_players_page(
    cb: CallbackQuery, session: AsyncSession, user: User
):
    page = int(cb.data.split(":")[1])
    await _show_players_page(cb.message, session, user, page=page, edit=True)
    await cb.answer()


@router.callback_query(F.data == "noop_players")
async def cb_noop_players(cb: CallbackQuery):
    await cb.answer()


@router.callback_query(F.data == "show_top")
async def cb_show_top(cb: CallbackQuery, session: AsyncSession, user: User):
    from app.repositories.user_repo import user_repo
    top     = await user_repo.get_top_by_power(session, 10)
    my_rank = await user_repo.get_rank_by_power(session, user.id)

    lines  = ["🏆 <b>Топ-10 по боевой мощи</b>\n"]
    medals = {0: "🥇", 1: "🥈", 2: "🥉"}
    for i, u in enumerate(top):
        medal = medals.get(i, f"{i + 1}.")
        vvip  = " 👑" if u.ultra_instinct else ""
        lines.append(
            f"{medal} <b>{u.full_name}</b>{vvip}\n"
            f"   💪 {fmt_num(u.combat_power)} | "
            f"{_phase_emoji(u.phase)} {phase_label(u.phase)}"
        )
    lines.append(f"\n📍 Твоё место: #{my_rank}")

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="👥 Все игроки", callback_data="players_page:0"
    ))
    try:
        await cb.message.edit_text(
            "\n".join(lines),
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


# ── /admin ───────────────────────────────────────────────────────────────────

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