"""Тренировка техники — путь к каждому уровню уникальной техники (хендлеры).

🏋 Тренировки → 🥋 Тренировка техники → техника → оплатить тренировку у её учителя → квест →
поднять уровень за фрагменты (пользователь 2026-10-12). Логика — `services/unique_technique/training`.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.development import MAX_LEVEL
from bot.constant.training import CB_TRAIN_TECH_LEVEL_PREFIX, CB_TRAIN_TECH_OPEN, CB_TRAIN_TECH_PAY_PREFIX, CB_TRAIN_TECH_VIEW_PREFIX
from bot.keyboards.training import tech_list_menu, tech_menu
from bot.services.gang import get_gang
from bot.services.unique_technique import (
    NotEnoughFragmentsError,
    TechTraining,
    TechniqueMaxLevelError,
    TechniqueNotOwnedError,
    TrainingActiveError,
    TrainingCoinsError,
    TrainingRequiredError,
    get_training,
    level_up,
    list_trainings,
    start_training,
)
from bot.texts.dev_quest import render_tasks
from bot.texts.profile import NOT_ONBOARDED
from bot.texts.training import (
    BTN_TECH_ROW,
    TECH_ACTIVE_ALERT,
    TECH_LIST,
    TECH_LIST_EMPTY,
    TECH_MARK,
    TECH_NEED_TRAINING_ALERT,
    TECH_NOT_ENOUGH_COINS,
    TECH_PAID_ALERT,
    TECH_SCREEN,
    TECH_STAGE_LEVEL,
    TECH_STAGE_MAX,
    TECH_STAGE_PAY,
    TECH_STAGE_QUEST,
)
from bot.texts.unique_technique import LEVEL_UP_ALERT, NOT_ENOUGH_ALERT, TEACHER_NAMES, TECHNIQUE_NAMES
from bot.utils.formatting import format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="training_technique")


async def _guard(callback: CallbackQuery, session: AsyncSession) -> bool:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return False
    return True


async def _render_list(session: AsyncSession, user_id: int):
    rows, fragments, coins = await list_trainings(session, user_id)
    text = TECH_LIST.format(fragments=format_number(fragments), coins=format_number(coins)) + ("" if rows else TECH_LIST_EMPTY)
    buttons = [(r.code, BTN_TECH_ROW.format(mark=TECH_MARK[r.stage], name=TECHNIQUE_NAMES[r.code], level=r.level)) for r in rows]
    return text, tech_list_menu(buttons)


def _render_tech(row: TechTraining, fragments: int):
    have = format_number(fragments)
    if row.stage == "max":
        body = TECH_STAGE_MAX
    elif row.stage == "pay":
        body = TECH_STAGE_PAY.format(
            next=row.next_level, price=format_number(row.price), tasks=render_tasks(row.tasks, {}),
            fragments=format_number(row.fragments_cost), have=have,
        )
    elif row.stage == "quest":
        body = TECH_STAGE_QUEST.format(
            next=row.next_level, tasks=render_tasks(row.quest.tasks, row.quest.progress), fragments=format_number(row.fragments_cost),
        )
    else:
        body = TECH_STAGE_LEVEL.format(next=row.next_level, fragments=format_number(row.fragments_cost), have=have)
    text = TECH_SCREEN.format(
        name=TECHNIQUE_NAMES[row.code], level=row.level, max_level=MAX_LEVEL, teacher=TEACHER_NAMES[row.code], body=body,
    )
    return text, tech_menu(row.code, row.stage, next_level=row.next_level, price=row.price, fragments=row.fragments_cost)


async def _show_tech(callback: CallbackQuery, session: AsyncSession, code: str) -> None:
    try:
        row = await get_training(session, callback.from_user.id, code)
    except TechniqueNotOwnedError:
        text, markup = await _render_list(session, callback.from_user.id)
    else:
        _, fragments, _ = await list_trainings(session, callback.from_user.id)
        text, markup = _render_tech(row, fragments)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data == CB_TRAIN_TECH_OPEN)
async def cb_tech_list(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _guard(callback, session):
        return
    await callback.answer()
    text, markup = await _render_list(session, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_TRAIN_TECH_VIEW_PREFIX))
async def cb_tech_view(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _guard(callback, session):
        return
    await callback.answer()
    await _show_tech(callback, session, callback.data.removeprefix(CB_TRAIN_TECH_VIEW_PREFIX))


@router.callback_query(F.data.startswith(CB_TRAIN_TECH_PAY_PREFIX))
async def cb_tech_pay(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _guard(callback, session):
        return
    code = callback.data.removeprefix(CB_TRAIN_TECH_PAY_PREFIX)
    try:
        await start_training(session, callback.from_user.id, code)
    except (TechniqueNotOwnedError, TechniqueMaxLevelError):
        await callback.answer()
        return
    except TrainingActiveError:
        await callback.answer(TECH_ACTIVE_ALERT, show_alert=True)
        return
    except TrainingCoinsError as exc:
        await callback.answer(TECH_NOT_ENOUGH_COINS.format(cost=format_number(exc.cost), balance=format_number(exc.balance)), show_alert=True)
        return
    await callback.answer(TECH_PAID_ALERT)
    await _show_tech(callback, session, code)


@router.callback_query(F.data.startswith(CB_TRAIN_TECH_LEVEL_PREFIX))
async def cb_tech_level(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _guard(callback, session):
        return
    code = callback.data.removeprefix(CB_TRAIN_TECH_LEVEL_PREFIX)
    try:
        level = await level_up(session, callback.from_user.id, code)
    except (TechniqueNotOwnedError, TechniqueMaxLevelError):
        await callback.answer()
        return
    except TrainingRequiredError:
        await callback.answer(TECH_NEED_TRAINING_ALERT, show_alert=True)
        return
    except NotEnoughFragmentsError as exc:
        await callback.answer(NOT_ENOUGH_ALERT.format(cost=exc.cost, have=exc.have), show_alert=True)
        return
    await callback.answer(LEVEL_UP_ALERT.format(name=TECHNIQUE_NAMES[code], level=level), show_alert=True)
    await _show_tech(callback, session, code)
