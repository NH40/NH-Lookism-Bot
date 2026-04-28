from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.skill import UserMastery
from app.services.training_service import training_service
from app.services.cooldown_service import cooldown_service
from app.utils.keyboards.common import back_kb
from app.utils.formatters import fmt_num

router = Router()


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
        text="◀️ Назад", callback_data="main_menu"
    ))

    r = await session.execute(
        select(UserMastery).where(UserMastery.user_id == user.id)
    )
    mastery = r.scalar_one_or_none()

    from app.data.skills import MASTERY
    bonus_map = {0: 0, 1: 5, 2: 10, 3: 20, 4: 30}
    speed_map = {0: 0, 1: 5, 2: 10, 3: 15, 4: 20}
    mastery_lines = []
    for m in MASTERY:
        current = getattr(mastery, m.skill_id, 0) if mastery else 0
        max_level = 4
        if m.skill_id in ("strength", "technique"):
            bonus = bonus_map.get(current, 0)
        else:
            bonus = speed_map.get(current, 0)
        mastery_lines.append(
            f"  {m.emoji} {m.name}: {current}/{max_level} (+{bonus}%)"
        )

    await cb.message.edit_text(
        f"🏋 <b>Тренировка</b>\n\n"
        f"⭐ Очки мастерства: <b>{user.mastery_points}</b>\n"
        f"<i>Прокачка мастерства → Навыки → Мастерство</i>\n\n"
        f"<b>Текущее мастерство:</b>\n"
        + "\n".join(mastery_lines)
        + "\n\n<b>Выбери тренера:</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


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
            f"Используй очки в разделе <b>Навыки → Мастерство</b>",
            reply_markup=back_kb("training_menu"),
            parse_mode="HTML",
        )
    else:
        await cb.answer("Тренер не найден", show_alert=True)


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