"""Пробуждение — экран, квест кулака, подтверждение в два нажатия (хендлеры).

Вход — «🌀 Пробуждение» на экране «📈 Развитие».
"""
from __future__ import annotations

from bot.keyboards.common import back_menu

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.awakening import LEVELS
from bot.config.development import awakening_multiplier
from bot.constant.awakening import CB_AWAKEN_ASK, CB_AWAKEN_CONFIRM, CB_AWAKEN_OPEN, CB_AWAKEN_RELOCATE
from bot.keyboards.awakening import awakening_menu, confirm_menu
from bot.services.awakening import (
    AwakeningMaxedError,
    ConfirmExpiredError,
    NotEmperorError,
    QuestNotCompleteError,
    awaken,
    get_view,
    request,
)
from bot.services.gang import get_gang
from bot.texts.awakening import (
    AWAKENED,
    CONFIRM_EXPIRED_ALERT,
    CONFIRM_SCREEN,
    LEVEL_LINE_DONE,
    LEVEL_LINE_LOCKED,
    MAXED_ALERT,
    NOT_EMPEROR_ALERT,
    QUEST_NOT_DONE_ALERT,
    SCREEN,
    STATUS_MAXED,
    STATUS_NOT_EMPEROR,
    STATUS_QUEST,
    STATUS_READY,
)
from bot.texts.dev_quest import render_tasks
from bot.texts.development import describe_level
from bot.texts.profile import NOT_ONBOARDED, POTENTIAL_LABELS
from bot.utils.safe_edit import safe_clear_markup, safe_edit_text

router = Router(name="awakening")


def _mult(level: int) -> str:
    return f"{awakening_multiplier(level):g}"


async def render_awakening(session: AsyncSession, user_id: int):
    view = await get_view(session, user_id)
    levels = "\n".join(
        (LEVEL_LINE_DONE if n <= view.level else LEVEL_LINE_LOCKED).format(n=n, mult=_mult(n), effect=describe_level(spec))
        for n, spec in enumerate(LEVELS, 1)
    )
    if view.maxed:
        status = STATUS_MAXED
    elif not view.is_emperor:
        status = STATUS_NOT_EMPEROR
    elif view.ready:
        status = STATUS_READY.format(next_mult=_mult(view.level + 1), blood=view.next_blood, floor=POTENTIAL_LABELS[view.next_floor])
    else:
        status = STATUS_QUEST.format(next=view.level + 1, tasks=render_tasks(view.quest.tasks, view.quest.progress) if view.quest else "—")
    text = SCREEN.format(level=view.level, multiplier=_mult(view.level), levels=levels, status=status)
    return text, awakening_menu(ready=view.ready)


@router.callback_query(F.data == CB_AWAKEN_OPEN)
async def cb_awaken_open(callback: CallbackQuery, session: AsyncSession) -> None:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return
    await callback.answer()
    text, markup = await render_awakening(session, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data == CB_AWAKEN_ASK)
async def cb_awaken_ask(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    # Popup-тексты — без HTML.
    try:
        seconds = await request(session, redis, callback.from_user.id)
    except AwakeningMaxedError:
        await callback.answer(MAXED_ALERT, show_alert=True)
        return
    except NotEmperorError:
        await callback.answer(NOT_EMPEROR_ALERT, show_alert=True)
        return
    except QuestNotCompleteError:
        await callback.answer(QUEST_NOT_DONE_ALERT, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(callback.message, CONFIRM_SCREEN.format(seconds=seconds), reply_markup=confirm_menu())


@router.callback_query(F.data == CB_AWAKEN_CONFIRM)
async def cb_awaken_confirm(callback: CallbackQuery, session: AsyncSession, redis: Redis, state: FSMContext) -> None:
    try:
        result = await awaken(session, redis, callback.from_user.id)
    except ConfirmExpiredError:
        await callback.answer(CONFIRM_EXPIRED_ALERT, show_alert=True)
        return
    except NotEmperorError:
        await callback.answer(NOT_EMPEROR_ALERT, show_alert=True)
        return
    except (QuestNotCompleteError, AwakeningMaxedError):
        await callback.answer(QUEST_NOT_DONE_ALERT, show_alert=True)
        return
    await state.clear()
    await callback.answer()
    await safe_clear_markup(callback.message)
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    from bot.services.awakening import allow_relocate
    from bot.texts.awakening import BTN_RELOCATE, RELOCATE_HINT

    await allow_relocate(redis, callback.from_user.id)
    markup = back_menu(CB_AWAKEN_OPEN)
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=BTN_RELOCATE, callback_data=CB_AWAKEN_RELOCATE)], *markup.inline_keyboard])
    await callback.message.answer(
        AWAKENED.format(
            level=result.level, multiplier=f"{result.multiplier:g}",
            potential=POTENTIAL_LABELS[result.potential], blood=result.blood,
        ) + RELOCATE_HINT,
        reply_markup=markup,
    )



@router.callback_query(F.data == CB_AWAKEN_RELOCATE)
async def cb_awaken_relocate(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    from bot.keyboards.start import country_menu
    from bot.services.awakening import RelocateExpiredError, RelocateHasDistrictsError, relocate
    from bot.texts.awakening import RELOCATE_EXPIRED_ALERT, RELOCATE_HAS_DISTRICTS_ALERT, RELOCATE_PICK

    try:
        await relocate(session, redis, callback.from_user.id)
    except RelocateExpiredError:
        await callback.answer(RELOCATE_EXPIRED_ALERT, show_alert=True)
        return
    except RelocateHasDistrictsError:
        await callback.answer(RELOCATE_HAS_DISTRICTS_ALERT, show_alert=True)
        return
    await callback.answer()
    await safe_clear_markup(callback.message)
    await callback.message.answer(RELOCATE_PICK, reply_markup=country_menu())
