"""Тренировки — личная (очки развития по потенциалу, КД 1 час) и тренировка статистов (3 этапа: прокачка мощи / пробуждение звёзд / повышение ранга) (хендлеры).

Личная тренировка — кнопка на экране тренировок и на экране характеристик профиля.
"""
from __future__ import annotations

from bot.keyboards.common import back_menu

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.training import CB_TRAIN_EXTRAS_OPEN, CB_TRAIN_EXTRAS_RUN, CB_TRAIN_PERSONAL
from bot.db.repositories.user import get_by_id
from bot.keyboards.training import personal_result_menu, train_menu
from bot.services.extra import get_army_stats
from bot.services.characteristic import get_stats_view
from bot.services.training import TrainingOnCooldownError, personal_cooldown_left, train_extras, train_personal
from bot.texts.common import render_army_block
from bot.texts.profile import NOT_ONBOARDED
from bot.texts.profile import POTENTIAL_LABELS
from bot.texts.training import (
    PERSONAL_COOLDOWN,
    PERSONAL_COOLDOWN_LINE,
    PERSONAL_GAINED,
    PERSONAL_NOTHING,
    PERSONAL_READY,
    PERSONAL_RESULT,
    TRAIN_COOLDOWN,
    TRAIN_MENU_HEADER,
    TRAIN_NO_EXTRAS,
    TRAIN_RESULT,
)
from bot.utils.formatting import format_countdown, format_number

router = Router(name="training")


async def show_train_menu(message: Message, session: AsyncSession, user_id: int, redis: Redis) -> None:
    """Публичная функция домена — переиспользуется главным меню профиля (кнопка
    "🏋️ Тренировка"), тот же паттерн, что `show_recruit_menu`."""
    stats = await get_army_stats(session, user_id)
    army_block = render_army_block(
        total_quantity=stats.total_quantity,
        total_power=stats.total_power,
        attack_quantity=stats.attack.quantity,
        defense_quantity=stats.defense.quantity,
        by_rank=stats.by_rank,
        cards_quantity=stats.cards_quantity,
    )
    view = await get_stats_view(session, user_id)
    left = await personal_cooldown_left(redis, user_id)
    personal_line = (
        PERSONAL_COOLDOWN_LINE.format(countdown=format_countdown(left), points=format_number(view.dev_points))
        if left
        else PERSONAL_READY.format(potential=POTENTIAL_LABELS[view.potential], points=format_number(view.dev_points))
    )
    await message.answer(
        TRAIN_MENU_HEADER.format(personal_line=personal_line, army_block=army_block), reply_markup=train_menu()
    )


@router.message(Command("train"))
async def cmd_train(message: Message, session: AsyncSession, redis: Redis) -> None:
    user = await get_by_id(session, message.from_user.id)
    if user is None or user.city_id is None:
        await message.answer(NOT_ONBOARDED)
        return
    await show_train_menu(message, session, user.id, redis)


@router.callback_query(F.data == CB_TRAIN_EXTRAS_OPEN)
async def cb_train_open(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    user = await get_by_id(session, callback.from_user.id)
    if user is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    await callback.answer()
    await show_train_menu(callback.message, session, user.id, redis)


@router.callback_query(F.data == CB_TRAIN_EXTRAS_RUN)
async def cb_train_run(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    user = await get_by_id(session, callback.from_user.id)
    if user is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return

    try:
        result = await train_extras(session, redis, user.id, user.phase)
    except TrainingOnCooldownError as exc:
        await callback.answer(
            TRAIN_COOLDOWN.format(countdown=format_countdown(exc.retry_after_seconds)),
            show_alert=True,
        )
        return

    await callback.answer()
    if result.attempted == 0:
        await callback.message.answer(TRAIN_NO_EXTRAS, reply_markup=back_menu(CB_TRAIN_EXTRAS_OPEN))
        return
    await callback.message.answer(
        TRAIN_RESULT.format(
            attempted=format_number(result.attempted),
            stage1=format_number(result.stage1),
            stage2=format_number(result.stage2),
            stage3=format_number(result.stage3),
        )
    , reply_markup=back_menu(CB_TRAIN_EXTRAS_OPEN))
    await show_train_menu(callback.message, session, user.id, redis)


@router.callback_query(F.data == CB_TRAIN_PERSONAL)
async def cb_train_personal(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    user = await get_by_id(session, callback.from_user.id)
    if user is None or user.city_id is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    try:
        result = await train_personal(session, redis, user.id)
    except TrainingOnCooldownError as exc:
        # Popup — без HTML.
        await callback.answer(PERSONAL_COOLDOWN.format(countdown=format_countdown(exc.retry_after_seconds)), show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(
        PERSONAL_RESULT.format(
            outcome=PERSONAL_GAINED.format(gained=result.points) if result.points else PERSONAL_NOTHING,
            potential=POTENTIAL_LABELS[result.potential],
            points=format_number(result.dev_points),
            countdown=format_countdown(result.cooldown_seconds),
        ),
        reply_markup=personal_result_menu(),
    )
