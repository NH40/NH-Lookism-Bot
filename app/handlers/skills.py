from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.skill import UserMastery
from app.services.skill_service import skill_service
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_num, skill_path_label
from app.data.skills import MASTERY, MASTERY_BY_ID, PATH_SKILLS

router = Router()


MASTERY_DESCRIPTIONS = {
    "strength":   "Повышает общую боевую мощь",
    "speed":      "Ускоряет доход, вербовку и тренировки",
    "endurance":  "Позволяет побеждать более сильных противников",
    "technique":  "Улучшает эффективность тренировок",
}

MASTERY_LEVEL_NAMES = {
    0: "Нету",
    1: "I",
    2: "II",
    3: "III",
    4: "IV",
}


@router.callback_query(F.data == "skills")
async def cb_skills(cb: CallbackQuery, session: AsyncSession, user: User):
    r = await session.execute(
        select(UserMastery).where(UserMastery.user_id == user.id)
    )
    mastery = r.scalar_one_or_none()

    path_emoji = {
        "businessman": "💼", "romantic": "💝", "monster": "👹"
    }.get(user.skill_path, "❓") if user.skill_path else "❓"

    ui_status = "✅ Активен" if (user.ultra_instinct or user.true_ultra_instinct) else "❌"

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⚔️ Мастерство",     callback_data="mastery_menu"))
    builder.row(InlineKeyboardButton(text="🗺 Путь",            callback_data="path_menu" if user.skill_path else "path_choose"))
    builder.row(InlineKeyboardButton(text="👁 Ультра Инстинкт", callback_data="ui_settings"))
    builder.row(InlineKeyboardButton(text="◀️ Назад",           callback_data="main_menu"))

    text = (
        f"⚡ <b>Навыки</b>\n\n"
        f"💎 Очки пути: {user.skill_path_points}\n"
        f"🗺 Путь: {path_emoji} {skill_path_label(user.skill_path)}\n"
        f"👁 Ультра Инстинкт: {ui_status}\n\n"
        f"Выбери раздел:"
    )
    await cb.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data == "mastery_menu")
async def cb_mastery_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    r = await session.execute(
        select(UserMastery).where(UserMastery.user_id == user.id)
    )
    mastery = r.scalar_one_or_none()

    bonus_map  = {0: 0, 1: 5, 2: 10, 3: 20, 4: 30}
    speed_map  = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}

    def lvl(attr): return getattr(mastery, attr, 0) if mastery else 0
    def bmap(attr):
        return speed_map.get(lvl(attr), 0) if attr in ("speed", "endurance") \
            else bonus_map.get(lvl(attr), 0)

    skills_info = [
        ("strength",  "⚔️ Сила",         f"+{bmap('strength')}%",  "Повышает общую боевую мощь"),
        ("speed",     "⚡ Скорость",      f"+{bmap('speed')}%",    "Ускоряет доход, вербовку и тренировки"),
        ("endurance", "🛡 Выносливость",  f"+{bmap('endurance')}%","Позволяет побеждать более сильных противников"),
        ("technique", "🏋 Техника",       f"+{bmap('technique')}%","Улучшает эффективность тренировок"),
    ]

    lines = [f"⚔️ <b>Мастерство</b>\n\n💰 Баланс: {fmt_num(user.nh_coins)} NHCoin\n"]

    builder = InlineKeyboardBuilder()
    for skill_id, label, bonus_str, desc in skills_info:
        cur = lvl(skill_id)
        level_name = MASTERY_LEVEL_NAMES.get(cur, str(cur))
        if cur < 4:
            next_cost = MASTERY_BY_ID[skill_id].levels[cur + 1].cost
            next_bonus = MASTERY_BY_ID[skill_id].levels[cur + 1].bonus
            cost_str = f"💰 {fmt_num(next_cost)}"
            lines.append(
                f"{'✅' if cur > 0 else '✅'} {label} — {level_name} ({bonus_str}) → {cost_str}\n"
                f"<i>{desc}</i>\n"
            )
            builder.button(
                text=f"{label} [{level_name}] | 💰 {fmt_num(next_cost)}",
                callback_data=f"mastery_upgrade:{skill_id}"
            )
        else:
            lines.append(f"✅ {label} — MAX ({bonus_str})\n<i>{desc}</i>\n")

    builder.adjust(1)
    builder.row(InlineKeyboardButton(
        text="Нажми на навык чтобы улучшить:", callback_data="noop"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="skills"))

    await cb.message.edit_text(
        "\n".join(lines) + "\nНажми на навык чтобы улучшить:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()


@router.callback_query(F.data.startswith("mastery_upgrade:"))
async def cb_mastery_upgrade(cb: CallbackQuery, session: AsyncSession, user: User):
    skill_id = cb.data.split(":")[1]
    result = await skill_service.upgrade_mastery(session, user, skill_id)
    if result["ok"]:
        await cb.answer(f"✅ Улучшено! +{result['bonus']}%")
        await cb_mastery_menu(cb, session, user)
    else:
        await cb.answer(result["reason"], show_alert=True)


@router.callback_query(F.data == "path_choose")
async def cb_path_choose(cb: CallbackQuery, session: AsyncSession, user: User):
    if user.skill_path:
        await cb.answer("Путь уже выбран", show_alert=True)
        await cb_path_menu(cb, session, user)
        return

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="💼 Бизнесмен", callback_data="choose_path:businessman"
    ))
    builder.row(InlineKeyboardButton(
        text="💝 Романтик", callback_data="choose_path:romantic"
    ))
    builder.row(InlineKeyboardButton(
        text="👹 Монстр", callback_data="choose_path:monster"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="skills"))

    await cb.message.edit_text(
        "🗺 <b>Выбор пути</b>\n\n"
        "💼 <b>Бизнесмен</b>\n+% доход, скидки на здания, множитель районов\n\n"
        "💝 <b>Романтик</b>\n+слоты тикетов, +% шанс, двойная вербовка\n\n"
        "👹 <b>Монстр</b>\n+% тренировка, двойная тренировка, двойная атака\n\n"
        "<i>Выбор нельзя изменить!</i>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("choose_path:"))
async def cb_choose_path(cb: CallbackQuery, session: AsyncSession, user: User):
    path = cb.data.split(":")[1]
    result = await skill_service.choose_path(session, user, path)
    if result["ok"]:
        await cb.answer(f"✅ Путь выбран!")
        await cb_path_menu(cb, session, user)
    else:
        await cb.answer(result["reason"], show_alert=True)


@router.callback_query(F.data == "path_menu")
async def cb_path_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    if not user.skill_path:
        await cb_path_choose(cb, session, user)
        return

    bought = await skill_service.get_path_skills_bought(session, user.id)
    skills = PATH_SKILLS.get(user.skill_path, [])

    path_emoji = {
        "businessman": "💼", "romantic": "💝", "monster": "👹"
    }.get(user.skill_path, "")

    builder = InlineKeyboardBuilder()
    lines = [
        f"🗺 <b>Путь: {path_emoji} {skill_path_label(user.skill_path)}</b>\n\n"
        f"💎 Очков пути: {user.skill_path_points}\n"
    ]

    for skill in skills:
        is_bought = skill.skill_id in bought
        status = "✅" if is_bought else f"🔷 {skill.cost} очков"
        lines.append(f"{skill.emoji} {skill.name} [{status}]\n  └ {skill.description}")
        if not is_bought:
            builder.button(
                text=f"{skill.emoji} {skill.name} | 🔷 {skill.cost}",
                callback_data=f"buy_path_skill:{skill.skill_id}"
            )

    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="skills"))

    await cb.message.edit_text(
        "\n".join(lines),
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("buy_path_skill:"))
async def cb_buy_path_skill(cb: CallbackQuery, session: AsyncSession, user: User):
    skill_id = cb.data.split(":")[1]
    result = await skill_service.buy_path_skill(session, user, skill_id)
    if result["ok"]:
        await cb.answer(f"✅ Навык '{result['skill']}' куплен!")
        await cb_path_menu(cb, session, user)
    else:
        await cb.answer(result["reason"], show_alert=True)


@router.callback_query(F.data == "ui_settings")
async def cb_ui_settings(cb: CallbackQuery, session: AsyncSession, user: User):
    if not user.ultra_instinct and not user.true_ultra_instinct:
        await cb.message.edit_text(
            "👁 <b>Ультра Инстинкт</b>\n\n"
            "❌ Не активирован\n\n"
            "Доступен при покупке донат-титула UI",
            reply_markup=back_kb("skills"),
            parse_mode="HTML",
        )
        return

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=f"{'✅' if user.ui_auto_recruit else '❌'} Авто-вербовка",
        callback_data="toggle_ui_recruit"
    ))
    builder.row(InlineKeyboardButton(
        text=f"{'✅' if user.ui_auto_train else '❌'} Авто-тренировка",
        callback_data="toggle_ui_train"
    ))
    builder.row(InlineKeyboardButton(
        text=f"{'✅' if user.ui_auto_ticket else '❌'} Авто-тикеты",
        callback_data="toggle_ui_ticket"
    ))
    builder.row(InlineKeyboardButton(
        text=f"{'✅' if user.ui_auto_pull else '❌'} Авто-прокрутка персонажей",
        callback_data="toggle_ui_pull"
    ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="skills"))

    tui_str = " | TUI ✅" if user.true_ultra_instinct else ""
    await cb.message.edit_text(
        f"👁 <b>Ультра Инстинкт</b>{tui_str}\n\n"
        f"✅ Активирован!\n\n"
        f"Настройки автоматизации:\n"
        f"{'✅' if user.ui_auto_recruit else '❌'} Авто-вербовка\n"
        f"{'✅' if user.ui_auto_train else '❌'} Авто-тренировка\n"
        f"{'✅' if user.ui_auto_ticket else '❌'} Авто-тикеты\n"
        f"{'✅' if user.ui_auto_pull else '❌'} Авто-прокрутка персонажей",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "toggle_ui_recruit")
async def toggle_ui_recruit(cb: CallbackQuery, session: AsyncSession, user: User):
    user.ui_auto_recruit = not user.ui_auto_recruit
    await session.flush()
    await cb_ui_settings(cb, session, user)


@router.callback_query(F.data == "toggle_ui_train")
async def toggle_ui_train(cb: CallbackQuery, session: AsyncSession, user: User):
    user.ui_auto_train = not user.ui_auto_train
    await session.flush()
    await cb_ui_settings(cb, session, user)


@router.callback_query(F.data == "toggle_ui_ticket")
async def toggle_ui_ticket(cb: CallbackQuery, session: AsyncSession, user: User):
    user.ui_auto_ticket = not user.ui_auto_ticket
    await session.flush()
    await cb_ui_settings(cb, session, user)


@router.callback_query(F.data == "toggle_ui_pull")
async def toggle_ui_pull(cb: CallbackQuery, session: AsyncSession, user: User):
    user.ui_auto_pull = not user.ui_auto_pull
    await session.flush()
    await cb_ui_settings(cb, session, user)