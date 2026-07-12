from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.skill import UserMastery
from app.data.skills import MASTERY_BY_ID
from app.utils.formatters import progress_bar

router = Router()


MASTERY_LEVEL_NAMES = {
    0: "Нету",
    1: "I",
    2: "II",
    3: "III",
    4: "IV",
}


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

    war_points = getattr(user, "war_points", 0)
    war_genius = getattr(user, "war_genius_level", 0)
    lines = [
        f"⚔️ <b>Мастерство</b>\n",
        f"⭐ Очков мастерства: <b>{user.mastery_points}</b>",
        f"⚔️ Очков войны: <b>{war_points}</b>   🎖 Гений войны {progress_bar(war_genius, 5)} {war_genius}/5",
        f"<i>Мастерство — у Тома Ли | Очки войны — у Менеджера Кима</i>",
        f"",
        f"━━━ 📊 Ветки ━━━",
    ]

    builder = InlineKeyboardBuilder()
    for skill_id, label, desc in skills_info:
        cur = lvl(skill_id)
        bonus = bmap(skill_id)
        level_name = MASTERY_LEVEL_NAMES.get(cur, str(cur))
        max_level = 4
        bar = progress_bar(cur, max_level)

        if cur < max_level:
            next_level = cur + 1
            cost = next_level
            can_buy = user.mastery_points >= cost
            afford = "✅" if can_buy else "❌"
            lines.append(f"{afford} {label} {bar} {level_name} (+{bonus}%)")
            lines.append(f"   {desc} · след: {cost}⭐")
            builder.button(
                text=f"{label} [{level_name}→{next_level}] | ⭐ {cost}",
                callback_data=f"mastery_upgrade:{skill_id}"
            )
        else:
            lines.append(f"✅ {label} {bar} MAX (+{bonus}%)")
            lines.append(f"   {desc}")

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
    cost = next_level

    if user.mastery_points < cost:
        await cb.answer(
            f"Недостаточно очков мастерства (нужно {cost} ⭐, есть {user.mastery_points})",
            show_alert=True
        )
        return

    user.mastery_points -= cost
    setattr(mastery, skill_id, next_level)

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
