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

    ui_status = "✅ Активен" if (user.ultra_instinct or user.true_ultra_instinct or user.ui_is_donat or user.ui_level > 0) else "❌"

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

    bonus_map = {0: 0, 1: 5, 2: 10, 3: 20, 4: 30}
    speed_map = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}

    def lvl(attr): return getattr(mastery, attr, 0) if mastery else 0
    def bmap(attr):
        return speed_map.get(lvl(attr), 0) if attr in ("speed", "endurance") \
            else bonus_map.get(lvl(attr), 0)

    skills_info = [
        ("strength",  "⚔️ Сила",        "Повышает общую боевую мощь"),
        ("speed",     "⚡ Скорость",     "Уменьшает КД, вербовку и тренировки а также тикеты"),
        ("endurance", "🛡 Выносливость", "Позволяет побеждать более сильных противников"),
        ("technique", "🏋 Техника",      "Улучшает эффективность тренировок"),
    ]

    lines = [
        f"⚔️ <b>Мастерство</b>\n\n"
        f"⭐ Очков мастерства: <b>{user.mastery_points}</b>\n"
        f"<i>Очки получаются у тренера Тома Ли</i>\n"
        f"<i>Стоимость: уровень = кол-во очков (1→2 = 2 очка)</i>\n\n"
    ]

    builder = InlineKeyboardBuilder()
    for skill_id, label, desc in skills_info:
        cur = lvl(skill_id)
        bonus = bmap(skill_id)
        level_name = MASTERY_LEVEL_NAMES.get(cur, str(cur))
        max_level = 4

        if cur < max_level:
            next_level = cur + 1
            cost = next_level  # стоимость = номер следующего уровня
            can_buy = user.mastery_points >= cost
            afford = "✅" if can_buy else "❌"
            lines.append(
                f"{afford} {label} — {level_name} (+{bonus}%)\n"
                f"  └ {desc}\n"
                f"  └ Следующий уровень: {cost} ⭐\n"
            )
            builder.button(
                text=f"{label} [{level_name}→{next_level}] | ⭐ {cost}",
                callback_data=f"mastery_upgrade:{skill_id}"
            )
        else:
            lines.append(
                f"✅ {label} — MAX (+{bonus}%)\n"
                f"  └ {desc}\n"
            )

    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="skills"))

    await cb.message.edit_text(
        "\n".join(lines),
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("mastery_upgrade:"))
async def cb_mastery_upgrade(cb: CallbackQuery, session: AsyncSession, user: User):
    skill_id = cb.data.split(":")[1]

    cfg = MASTERY_BY_ID.get(skill_id)
    if not cfg:
        await cb.answer("Навык не найден", show_alert=True)
        return

    r = await session.execute(
        select(UserMastery).where(UserMastery.user_id == user.id)
    )
    mastery = r.scalar_one_or_none()
    if not mastery:
        mastery = UserMastery(user_id=user.id)
        session.add(mastery)
        await session.flush()

    current = getattr(mastery, skill_id, 0)
    max_level = 4

    if current >= max_level:
        await cb.answer("Максимальный уровень!", show_alert=True)
        return

    next_level = current + 1
    cost = next_level  # стоимость = номер следующего уровня

    if user.mastery_points < cost:
        await cb.answer(
            f"Недостаточно очков мастерства (нужно {cost} ⭐, есть {user.mastery_points})",
            show_alert=True
        )
        return

    # Списываем очки
    user.mastery_points -= cost
    setattr(mastery, skill_id, next_level)

    # Применяем бонус
    bonus_map = {0: 0, 1: 5, 2: 10, 3: 20, 4: 30}
    speed_map = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}
    old_bonus = bonus_map.get(current, 0) if skill_id in ("strength", "technique") \
        else speed_map.get(current, 0)
    new_bonus = bonus_map.get(next_level, 0) if skill_id in ("strength", "technique") \
        else speed_map.get(next_level, 0)
    delta = new_bonus - old_bonus

    if skill_id == "technique":
        user.income_bonus_percent += delta
        user.train_bonus_percent += delta
    elif skill_id == "strength":
        from app.repositories.squad_repo import squad_repo
        await squad_repo.update_user_combat_power(session, user)

    await session.flush()

    level_name = MASTERY_LEVEL_NAMES.get(next_level, str(next_level))
    await cb.answer(
        f"✅ {cfg.emoji} {cfg.name} → {level_name} (+{new_bonus}%)",
        show_alert=True
    )
    await cb_mastery_menu(cb, session, user)

@router.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()

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
    if not user.ultra_instinct and not user.true_ultra_instinct and user.ui_level == 0 and not user.ui_is_donat:
        await cb.message.edit_text(
            "👁 <b>Ультра Инстинкт</b>\n\n"
            "❌ Не активирован\n\n"
            "Получи УИ в разделе <b>Рейды → Крафт</b>\n"
            "или купи донат-титул UI",
            reply_markup=back_kb("skills"),
            parse_mode="HTML",
        )
        return

    builder = InlineKeyboardBuilder()

    has_1 = user.ui_level >= 1 or user.ui_is_donat
    has_2 = user.ui_level >= 2 or user.ui_is_donat
    has_3 = user.ui_level >= 3 or user.ui_is_donat
    has_4 = user.ui_level >= 4 or user.ui_is_donat

    if has_1:
        builder.row(InlineKeyboardButton(
            text=f"{'✅' if user.ui_auto_recruit else '❌'} Авто-вербовка",
            callback_data="toggle_ui_recruit"
        ))
    else:
        builder.row(InlineKeyboardButton(
            text="🔒 Авто-вербовка (УИ I)",
            callback_data="noop"
        ))

    if has_2:
        builder.row(InlineKeyboardButton(
            text=f"{'✅' if user.ui_auto_train else '❌'} Авто-тренировка",
            callback_data="toggle_ui_train"
        ))
    else:
        builder.row(InlineKeyboardButton(
            text="🔒 Авто-тренировка (УИ II)",
            callback_data="noop"
        ))

    if has_3:
        builder.row(InlineKeyboardButton(
            text=f"{'✅' if user.ui_auto_ticket else '❌'} Авто-тикеты",
            callback_data="toggle_ui_ticket"
        ))
    else:
        builder.row(InlineKeyboardButton(
            text="🔒 Авто-тикеты (УИ III)",
            callback_data="noop"
        ))

    if has_4:
        builder.row(InlineKeyboardButton(
            text=f"{'✅' if user.ui_auto_pull else '❌'} Авто-прокрутка персонажей",
            callback_data="toggle_ui_pull"
        ))
    else:
        builder.row(InlineKeyboardButton(
            text="🔒 Авто-прокрутка (УИ IV)",
            callback_data="noop"
        ))

    if user.donat_ui_potion:
        builder.row(InlineKeyboardButton(
            text=f"{'✅' if user.ui_auto_potion else '❌'} Авто-зелья",
            callback_data="toggle_ui_potion"
        ))
    else:
        builder.row(InlineKeyboardButton(
            text="🔒 Авто-зелья (Алхимик УИ)",
            callback_data="noop"
        ))

    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="skills"))

    ui_level_str = "Донат (макс)" if user.ui_is_donat else f"Уровень {user.ui_level}/4"
    tui_str = " | TUI 🔱" if user.true_ultra_instinct else ""

    potion_line = (
        f"{'✅' if user.ui_auto_potion else '❌'}" if user.donat_ui_potion else "🔒 (Алхимик УИ)"
    )

    text = (
        f"👁 <b>Ультра Инстинкт</b> — {ui_level_str}{tui_str}\n\n"
        f"Настройки автоматизации:\n"
        f"{'✅' if has_1 else '🔒'} Авто-вербовка" + (f": {'✅' if user.ui_auto_recruit else '❌'}" if has_1 else " (УИ I)") + "\n"
        + f"{'✅' if has_2 else '🔒'} Авто-тренировка" + (f": {'✅' if user.ui_auto_train else '❌'}" if has_2 else " (УИ II)") + "\n"
        + f"{'✅' if has_3 else '🔒'} Авто-тикеты" + (f": {'✅' if user.ui_auto_ticket else '❌'}" if has_3 else " (УИ III)") + "\n"
        + f"{'✅' if has_4 else '🔒'} Авто-прокрутка" + (f": {'✅' if user.ui_auto_pull else '❌'}" if has_4 else " (УИ IV)") + "\n"
        + f"🧪 Авто-зелья: {potion_line}"
    )

    try:
        await cb.message.edit_text(
            text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        pass

@router.callback_query(F.data == "toggle_ui_recruit")
async def toggle_ui_recruit(cb: CallbackQuery, session: AsyncSession, user: User):
    if user.ui_level < 1 and not user.ui_is_donat:
        await cb.answer("Нужен УИ I уровня!", show_alert=True)
        return
    user.ui_auto_recruit = not user.ui_auto_recruit
    await session.flush()
    await cb_ui_settings(cb, session, user)


@router.callback_query(F.data == "toggle_ui_train")
async def toggle_ui_train(cb: CallbackQuery, session: AsyncSession, user: User):
    if user.ui_level < 2 and not user.ui_is_donat:
        await cb.answer("Нужен УИ II уровня!", show_alert=True)
        return
    user.ui_auto_train = not user.ui_auto_train
    await session.flush()
    await cb_ui_settings(cb, session, user)


@router.callback_query(F.data == "toggle_ui_ticket")
async def toggle_ui_ticket(cb: CallbackQuery, session: AsyncSession, user: User):
    if user.ui_level < 3 and not user.ui_is_donat:
        await cb.answer("Нужен УИ III уровня!", show_alert=True)
        return
    user.ui_auto_ticket = not user.ui_auto_ticket
    await session.flush()
    await cb_ui_settings(cb, session, user)


@router.callback_query(F.data == "toggle_ui_pull")
async def toggle_ui_pull(cb: CallbackQuery, session: AsyncSession, user: User):
    if user.ui_level < 4 and not user.ui_is_donat:
        await cb.answer("Нужен УИ IV уровня!", show_alert=True)
        return
    user.ui_auto_pull = not user.ui_auto_pull
    await session.flush()
    await cb_ui_settings(cb, session, user)


@router.callback_query(F.data == "toggle_ui_potion")
async def toggle_ui_potion(cb: CallbackQuery, session: AsyncSession, user: User):
    if not user.donat_ui_potion:
        await cb.answer("Нужен донат-титул «Алхимик УИ»!", show_alert=True)
        return
    user.ui_auto_potion = not user.ui_auto_potion
    await session.flush()
    if user.ui_auto_potion:
        from app.services.potion_service import potion_service
        await potion_service.buy_missing(session, user)
    await cb_ui_settings(cb, session, user)