from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.skill import UserMastery
from app.services.training_service import training_service, TRAINERS
from app.services.cooldown_service import cooldown_service
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_num

router = Router()


def _mastery_kb(user_mastery: UserMastery | None) -> any:
    from app.data.skills import MASTERY
    builder = InlineKeyboardBuilder()
    for m in MASTERY:
        current = getattr(user_mastery, m.skill_id, 0) if user_mastery else 0
        max_level = len(m.levels) - 1
        if current >= max_level:
            builder.row(InlineKeyboardButton(
                text=f"{m.emoji} {m.name} {current}/{max_level} ✅ МАКС",
                callback_data="noop_training"
            ))
        else:
            next_cost = m.levels[current + 1].cost
            builder.row(InlineKeyboardButton(
                text=f"{m.emoji} {m.name} {current}/{max_level} — {next_cost} очков",
                callback_data=f"mastery_buy:{m.skill_id}"
            ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data="training_menu"
    ))
    return builder.as_markup()


# ── Меню тренировки ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "training_menu")
async def cb_training_menu(cb: CallbackQuery, session: AsyncSession, user: User):
    trainers_info = await training_service.get_trainers_info(user.id)

    builder = InlineKeyboardBuilder()
    for t in trainers_info:
        if t["on_cd"]:
            ttl_str = cooldown_service.format_ttl(t["ttl"])
            builder.row(InlineKeyboardButton(
                text=f"{t['emoji']} {t['name']} — ⏳ {ttl_str}",
                callback_data="noop_training"
            ))
        else:
            builder.row(InlineKeyboardButton(
                text=f"{t['emoji']} {t['name']} — {t['cost']:,} NHCoin",
                callback_data=f"train_with:{t['id']}"
            ))

    builder.row(InlineKeyboardButton(
        text="📊 Прокачать мастерство",
        callback_data="mastery_upgrade"
    ))
    builder.row(InlineKeyboardButton(
        text="◀️ Назад", callback_data="main_menu"
    ))

    r = await session.execute(
        select(UserMastery).where(UserMastery.user_id == user.id)
    )
    mastery = r.scalar_one_or_none()

    from app.data.skills import MASTERY
    mastery_lines = []
    bonus_map = {0: 0, 1: 5, 2: 10, 3: 20, 4: 30}
    speed_map = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}
    for m in MASTERY:
        current = getattr(mastery, m.skill_id, 0) if mastery else 0
        max_level = len(m.levels) - 1
        if m.skill_id in ("strength", "technique"):
            bonus = bonus_map.get(current, 0)
        else:
            bonus = speed_map.get(current, 0)
        mastery_lines.append(
            f"  {m.emoji} {m.name}: {current}/{max_level} (+{bonus}%)"
        )

    await cb.message.edit_text(
        f"🏋 <b>Тренировка</b>\n\n"
        f"🪙 Очки мастерства: <b>{user.mastery_points}</b>\n\n"
        f"<b>Текущее мастерство:</b>\n"
        + "\n".join(mastery_lines)
        + "\n\n<b>Выбери тренера:</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


# ── Тренировка с тренером ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("train_with:"))
async def cb_train_with(cb: CallbackQuery, session: AsyncSession, user: User):
    trainer_id = cb.data.split(":")[1]

    if trainer_id == "tom_lee":
        result = await training_service.train_with_tom(session, user)

        if not result["ok"]:
            await cb.answer(result["reason"], show_alert=True)
            return

        points = result["points"]
        await cb.message.edit_text(
            f"🥋 <b>Тренировка с Томом Ли завершена!</b>\n\n"
            f"💸 Потрачено: {fmt_num(result['cost'])} NHCoin\n"
            f"⭐ Получено очков мастерства: <b>+{points}</b>\n"
            f"📊 Всего очков: <b>{result['total_points']}</b>\n\n"
            f"⏳ КД: 2 часа\n\n"
            f"Используй очки для прокачки мастерства!",
            reply_markup=back_kb("training_menu"),
            parse_mode="HTML",
        )
    else:
        await cb.answer("Тренер не найден", show_alert=True)


# ── Прокачка мастерства ──────────────────────────────────────────────────────

@router.callback_query(F.data == "mastery_upgrade")
async def cb_mastery_upgrade(cb: CallbackQuery, session: AsyncSession, user: User):
    r = await session.execute(
        select(UserMastery).where(UserMastery.user_id == user.id)
    )
    mastery = r.scalar_one_or_none()

    await cb.message.edit_text(
        f"📊 <b>Прокачка мастерства</b>\n\n"
        f"⭐ Очков мастерства: <b>{user.mastery_points}</b>\n\n"
        f"Стоимость уровня = номер уровня очков мастерства\n"
        f"(1→2 стоит 2 очка, 2→3 стоит 3 очка и т.д.)\n\n"
        f"Выбери что прокачать:",
        reply_markup=_mastery_kb(mastery),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("mastery_buy:"))
async def cb_mastery_buy(cb: CallbackQuery, session: AsyncSession, user: User):
    skill_id = cb.data.split(":")[1]

    from app.data.skills import MASTERY_BY_ID
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
    max_level = len(cfg.levels) - 1

    if current >= max_level:
        await cb.answer("Максимальный уровень!", show_alert=True)
        return

    # Стоимость = номер следующего уровня
    next_level = current + 1
    cost = next_level  # 1 уровень = 1 очко, 2 = 2 очка и т.д.

    if user.mastery_points < cost:
        await cb.answer(
            f"Недостаточно очков мастерства (нужно {cost})",
            show_alert=True
        )
        return

    # Списываем очки и повышаем уровень
    user.mastery_points -= cost
    setattr(mastery, skill_id, next_level)

    # Применяем бонус мастерства
    await _apply_mastery_bonus(session, user, cfg, current, next_level)

    await session.flush()

    bonus_map = {0: 0, 1: 5, 2: 10, 3: 20, 4: 30}
    speed_map = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}
    if skill_id in ("strength", "technique"):
        bonus = bonus_map.get(next_level, 0)
    else:
        bonus = speed_map.get(next_level, 0)

    await cb.answer(
        f"✅ {cfg.emoji} {cfg.name} → {next_level}/{max_level} (+{bonus}%)",
        show_alert=True
    )

    # Перерисовываем
    r2 = await session.execute(
        select(UserMastery).where(UserMastery.user_id == user.id)
    )
    mastery_updated = r2.scalar_one_or_none()
    await cb.message.edit_text(
        f"📊 <b>Прокачка мастерства</b>\n\n"
        f"⭐ Очков мастерства: <b>{user.mastery_points}</b>\n\n"
        f"Стоимость уровня = номер уровня очков мастерства\n"
        f"(1→2 стоит 2 очка, 2→3 стоит 3 очка и т.д.)\n\n"
        f"Выбери что прокачать:",
        reply_markup=_mastery_kb(mastery_updated),
        parse_mode="HTML",
    )


async def _apply_mastery_bonus(
    session: AsyncSession, user: User, cfg, old_level: int, new_level: int
) -> None:
    """Применяет дельту бонуса при повышении уровня мастерства."""
    from app.repositories.squad_repo import squad_repo

    old_bonus = cfg.levels[old_level].bonus
    new_bonus = cfg.levels[new_level].bonus
    delta = new_bonus - old_bonus

    if cfg.skill_id == "strength":
        # Обновляем combat_power через squad_repo
        await squad_repo.update_user_combat_power(session, user)

    elif cfg.skill_id == "technique":
        user.income_bonus_percent += delta
        user.train_bonus_percent += delta

    # speed и endurance применяются динамически при расчётах


# ── Рейд ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "raid_menu")
async def cb_raid_menu(cb: CallbackQuery, user: User):
    await cb.message.edit_text(
        "⚔️ <b>Рейды</b>\n\n"
        "🔨 Рейды находятся в разработке!\n\n"
        "Следи за обновлениями.",
        reply_markup=back_kb("main_menu"),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "noop_training")
async def cb_noop_training(cb: CallbackQuery):
    await cb.answer()