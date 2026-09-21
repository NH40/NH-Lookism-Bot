"""Тренировки — личная (характеристики, КД 10 минут) и тренировка статистов (3 этапа: прокачка мощи / пробуждение звёзд / повышение ранга) (хендлеры).

Личная тренировка — TODO (см. `services/training`). Пока только тренировка статистов —
команда `/train`, до появления настоящего экрана «Банда».
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.training import CB_TRAIN_EXTRAS_OPEN, CB_TRAIN_EXTRAS_RUN
from bot.db.repositories.user import get_by_id
from bot.keyboards.training import train_menu
from bot.services.extra import get_army_stats
from bot.services.training import TrainingOnCooldownError, train_extras
from bot.texts.common import render_army_block
from bot.texts.profile import NOT_ONBOARDED
from bot.texts.training import TRAIN_COOLDOWN, TRAIN_MENU_HEADER, TRAIN_NO_EXTRAS, TRAIN_RESULT
from bot.utils.formatting import format_countdown, format_number

router = Router(name="training")


async def show_train_menu(message: Message, session: AsyncSession, user_id: int) -> None:
    """Публичная функция домена — переиспользуется главным меню профиля (кнопка
    "🏋️ Тренировка"), тот же паттерн, что `show_recruit_menu`."""
    stats = await get_army_stats(session, user_id)
    army_block = render_army_block(
        total_quantity=stats.total_quantity, total_power=stats.total_power, by_rank=stats.by_rank
    )
    await message.answer(TRAIN_MENU_HEADER.format(army_block=army_block), reply_markup=train_menu())


@router.message(Command("train"))
async def cmd_train(message: Message, session: AsyncSession) -> None:
    user = await get_by_id(session, message.from_user.id)
    if user is None or user.city_id is None:
        await message.answer(NOT_ONBOARDED)
        return
    await show_train_menu(message, session, user.id)


@router.callback_query(F.data == CB_TRAIN_EXTRAS_OPEN)
async def cb_train_open(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_by_id(session, callback.from_user.id)
    if user is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    await callback.answer()
    await show_train_menu(callback.message, session, user.id)


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
        await callback.message.answer(TRAIN_NO_EXTRAS)
        return
    await callback.message.answer(
        TRAIN_RESULT.format(
            attempted=format_number(result.attempted),
            stage1=format_number(result.stage1),
            stage2=format_number(result.stage2),
            stage3=format_number(result.stage3),
        )
    )
    await show_train_menu(callback.message, session, user.id)
