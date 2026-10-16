"""Админка → карточка игрока → 📅 Задания: засчитать одно или все (хендлеры).

Пользователь 2026-10-12: «добавь эту кнопку ещё в админ-панели после поиска игрока, чтобы админ
мог засчитать задания игроку — одно или все». Раздел «Развитие» (уровень admin). Логика и
перепроверка прав — `services/admin/testing`.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.admin import (
    CB_ADMIN_PLAYER_QUESTS_PREFIX,
    CB_ADMIN_QUEST_ALL_PREFIX,
    CB_ADMIN_QUEST_DAILY_PREFIX,
    CB_ADMIN_QUEST_DEV_PREFIX,
    SECTION_DEV,
)
from bot.handlers.admin.common import guard
from bot.handlers.admin.player_target import load_target, name_of, parse_args
from bot.keyboards.admin import player_quests_menu
from bot.services.admin.testing import NotAdminError, QuestGoneError, complete, list_open
from bot.texts.admin import (
    QUEST_DAILY_LINE,
    QUEST_DEV_LINE,
    QUEST_GONE_ALERT,
    QUESTS_DONE_ALERT,
    QUESTS_NONE,
    QUESTS_SCREEN,
)
from bot.texts.dev_quest import TASK_LABELS, quest_title
from bot.utils.formatting import format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="admin_quests")


async def _render(callback: CallbackQuery, session: AsyncSession, user) -> None:
    daily, dev = await list_open(session, user.id)
    daily_rows = [(q.slot, TASK_LABELS.get(q.task, q.task)) for q in daily]
    dev_rows = [(q.id, quest_title(q.kind, q.ref)) for q in dev]
    text = QUESTS_SCREEN.format(
        name=name_of(user),
        daily="\n".join(
            QUEST_DAILY_LINE.format(label=TASK_LABELS.get(q.task, q.task), progress=format_number(q.progress), target=format_number(q.target))
            for q in daily
        ) or QUESTS_NONE,
        dev="\n".join(QUEST_DEV_LINE.format(title=t) for _, t in dev_rows) or QUESTS_NONE,
    )
    await safe_edit_text(callback.message, text, reply_markup=player_quests_menu(user.id, daily_rows, dev_rows))


async def _target(callback: CallbackQuery, session: AsyncSession, prefix: str):
    if not await guard(callback, session, SECTION_DEV):
        return None, None
    parsed = parse_args(callback.data, prefix)
    user = await load_target(callback, session, parsed[1] if parsed else None)
    return (parsed[0] if parsed else None), user


@router.callback_query(F.data.startswith(CB_ADMIN_PLAYER_QUESTS_PREFIX))
async def cb_player_quests(callback: CallbackQuery, session: AsyncSession) -> None:
    _, user = await _target(callback, session, CB_ADMIN_PLAYER_QUESTS_PREFIX)
    if user is None:
        return
    await callback.answer()
    await _render(callback, session, user)


async def _do(callback: CallbackQuery, session: AsyncSession, user, **what) -> None:
    try:
        daily, dev = await complete(session, callback.from_user.id, user.id, **what)
    except NotAdminError:
        await callback.answer()
        return
    except QuestGoneError:
        await callback.answer(QUEST_GONE_ALERT, show_alert=True)
    else:
        await callback.answer(QUESTS_DONE_ALERT.format(daily=daily, dev=dev))
    await _render(callback, session, user)


@router.callback_query(F.data.startswith(CB_ADMIN_QUEST_DAILY_PREFIX))
async def cb_quest_daily(callback: CallbackQuery, session: AsyncSession) -> None:
    fields, user = await _target(callback, session, CB_ADMIN_QUEST_DAILY_PREFIX)
    if user is None or not fields or not fields[0].isdigit():
        if user is not None:
            await callback.answer()
        return
    await _do(callback, session, user, slot=int(fields[0]))


@router.callback_query(F.data.startswith(CB_ADMIN_QUEST_DEV_PREFIX))
async def cb_quest_dev(callback: CallbackQuery, session: AsyncSession) -> None:
    fields, user = await _target(callback, session, CB_ADMIN_QUEST_DEV_PREFIX)
    if user is None or not fields or not fields[0].isdigit():
        if user is not None:
            await callback.answer()
        return
    await _do(callback, session, user, dev_id=int(fields[0]))


@router.callback_query(F.data.startswith(CB_ADMIN_QUEST_ALL_PREFIX))
async def cb_quest_all(callback: CallbackQuery, session: AsyncSession) -> None:
    _, user = await _target(callback, session, CB_ADMIN_QUEST_ALL_PREFIX)
    if user is None:
        return
    await _do(callback, session, user)
