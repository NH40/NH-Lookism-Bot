"""Ивенты императора: запуск у императора, получение у подданных, итоги (хендлеры)."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.cache.keys import action_lock
from bot.config.game import ACTION_LOCK_MS
from bot.constant.empire import (
    CB_EVENTS_CLAIM_PREFIX,
    CB_EVENTS_HOURS_PREFIX,
    CB_EVENTS_KIND_PREFIX,
    CB_EVENTS_OPEN,
    CB_EVENTS_START_PREFIX,
    CB_EVENTS_SUBJECT,
    EVENT_COINS,
    EVENT_DAILY,
    EVENT_DRILL,
    EVENT_FEAST,
    EVENT_HOLIDAY,
    EVENT_KINDS,
    EVENT_STATISTS,
    EVENT_TOURNAMENT,
    LOCK_ACTION_EMPIRE_EVENT,
)
from bot.keyboards.empire.events import back_to_kind, confirm_menu, events_menu, kind_menu, subject_menu
from bot.services.empire import events as ev
from bot.services.empire.event_push import about, deliver_started, details, error_text, prompt
from bot.states.empire import EmpireStates
from bot.texts.empire import events as t
from bot.utils.formatting import format_countdown, format_number
from bot.utils.safe_edit import safe_edit_text

log = logging.getLogger(__name__)
router = Router(name="empire_events")
_tasks: set[asyncio.Task] = set()


def _left(until: datetime) -> str:
    return format_countdown(max(0, int((until - datetime.now(timezone.utc)).total_seconds())))


# --- император ---


async def _show_events(message, session: AsyncSession, user_id: int) -> None:
    views = await ev.kinds_view(session, user_id)
    subjects, active = await ev.subject_counts(session, user_id)
    lines = []
    for v in views:
        title = t.TITLES[v.kind]
        if v.active is not None:
            lines.append(t.KIND_LINE_ACTIVE.format(title=title, left=_left(v.active.ends_at)))
        elif v.cooldown_seconds:
            lines.append(t.KIND_LINE_CD.format(title=title, left=format_countdown(v.cooldown_seconds)))
        else:
            lines.append(t.KIND_LINE_READY.format(title=title))
    await safe_edit_text(
        message, t.EVENTS_SCREEN.format(subjects=format_number(subjects), active=format_number(active), lines="\n".join(lines)),
        reply_markup=events_menu(),
    )


@router.callback_query(F.data == CB_EVENTS_OPEN)
async def cb_events(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    try:
        await ev._ensure_emperor(session, callback.from_user.id)
    except ev.NotEmperorError:
        await callback.answer(t.NOT_EMPEROR_ALERT, show_alert=True)
        return
    await callback.answer()
    await _show_events(callback.message, session, callback.from_user.id)


@router.callback_query(F.data.startswith(CB_EVENTS_KIND_PREFIX))
async def cb_kind(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    kind = callback.data.removeprefix(CB_EVENTS_KIND_PREFIX)
    if kind not in EVENT_KINDS:
        await callback.answer()
        return
    await state.clear()
    view = next(v for v in await ev.kinds_view(session, callback.from_user.id) if v.kind == kind)
    if view.active is not None:
        a = view.active
        units = t.STATUS_UNITS.format(units=format_number(a.units)) if kind == EVENT_STATISTS else ""
        status = t.STATUS_ACTIVE.format(left=_left(a.ends_at), claims=a.claims, pool=format_number(a.pool), units=units)
    elif view.cooldown_seconds:
        status = t.STATUS_CD.format(left=format_countdown(view.cooldown_seconds))
    else:
        status = t.STATUS_READY
        if kind in (EVENT_COINS, EVENT_STATISTS, EVENT_TOURNAMENT, EVENT_DAILY):
            await state.set_state(EmpireStates.waiting_event)
            await state.update_data(event_kind=kind, event_hours=0)
            status += "\n\n" + prompt(kind)
    ready = view.active is None and not view.cooldown_seconds
    await callback.answer()
    await safe_edit_text(
        callback.message, t.KIND_SCREEN.format(title=t.TITLES[kind], about=about(kind), status=status),
        reply_markup=kind_menu(kind, ready=ready),
    )


def _parse_kind_hours(data: str, prefix: str) -> tuple[str, int] | None:
    kind, _, raw = data.removeprefix(prefix).partition(":")
    return (kind, int(raw)) if kind in EVENT_KINDS and raw.isdigit() else None


@router.callback_query(F.data.startswith(CB_EVENTS_HOURS_PREFIX))
async def cb_hours(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    parsed = _parse_kind_hours(callback.data, CB_EVENTS_HOURS_PREFIX)
    if parsed is None:
        await callback.answer()
        return
    kind, hours = parsed
    await callback.answer()
    if kind == EVENT_FEAST:
        await state.set_state(EmpireStates.waiting_event)
        await state.update_data(event_kind=kind, event_hours=hours)
        await safe_edit_text(callback.message, prompt(kind, hours), reply_markup=back_to_kind(kind))
        return
    if kind == EVENT_DRILL:
        _, active = await ev.subject_counts(session, callback.from_user.id)
        text = t.DRILL_CONFIRM.format(
            hours=hours, price=format_number(await ev.drill_price(session, callback.from_user.id, hours)), active=active
        )
    else:
        text = t.HOLIDAY_CONFIRM.format(hours=hours)
    await safe_edit_text(callback.message, text, reply_markup=confirm_menu(kind, hours))


async def _launch(bot: Bot, session: AsyncSession, redis: Redis, session_factory, user_id: int, kind: str, args: list[str], hours: int) -> str:
    """Запуск по виду; → текст для императора. Ошибки — исключения сервиса."""
    key = action_lock(user_id, LOCK_ACTION_EMPIRE_EVENT)
    if not await redis.set(key, "1", nx=True, px=ACTION_LOCK_MS):
        return t.BUSY
    try:
        if kind == EVENT_COINS:
            started = await ev.start_coins(session, user_id, int(args[0]), int(args[1]))
        elif kind == EVENT_STATISTS:
            started = await ev.start_statists(session, user_id, args[0].upper(), int(args[1]), int(args[2]))
        elif kind == EVENT_DAILY:
            started = await ev.start_daily(session, user_id, int(args[0]), int(args[1]))
        elif kind == EVENT_TOURNAMENT:
            started = await ev.start_tournament(session, user_id, int(args[0]))
        elif kind == EVENT_FEAST:
            started = await ev.start_feast(session, user_id, hours, int(args[0]))
        elif kind == EVENT_DRILL:
            started = await ev.start_drill(session, user_id, hours)
        else:
            started = await ev.start_holiday(session, user_id, hours)
    finally:
        await redis.delete(key)
    task = asyncio.create_task(deliver_started(bot, session_factory, started))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return t.STARTED.format(title=t.TITLES[kind], cost=format_number(started.cost))


_ERRORS = (
    ev.NotEmperorError, ev.EventActiveError, ev.EventCooldownError, ev.NotEnoughCoinsError, ev.NoSubjectsError,
    ev.BadParamsError, ValueError, IndexError,
)


@router.message(EmpireStates.waiting_event, F.text)
async def msg_event(
    message: Message, session: AsyncSession, redis: Redis, state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    data = await state.get_data()
    kind, hours = data.get("event_kind"), int(data.get("event_hours") or 0)
    if kind not in EVENT_KINDS:
        await state.clear()
        return
    try:
        text = await _launch(message.bot, session, redis, session_factory, message.from_user.id, kind, message.text.split(), hours)
    except _ERRORS as exc:
        await session.rollback()
        await message.answer(error_text(exc, kind, hours), reply_markup=back_to_kind(kind))
        return
    await state.clear()
    await message.answer(text, reply_markup=back_to_kind(kind))


@router.callback_query(F.data.startswith(CB_EVENTS_START_PREFIX))
async def cb_start(
    callback: CallbackQuery, session: AsyncSession, redis: Redis, session_factory: async_sessionmaker[AsyncSession],
) -> None:
    parsed = _parse_kind_hours(callback.data, CB_EVENTS_START_PREFIX)
    if parsed is None or parsed[0] not in (EVENT_DRILL, EVENT_HOLIDAY):
        await callback.answer()
        return
    kind, hours = parsed
    try:
        text = await _launch(callback.bot, session, redis, session_factory, callback.from_user.id, kind, [], hours)
    except _ERRORS as exc:
        await session.rollback()
        await callback.answer(error_text(exc, kind, hours), show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(callback.message, text, reply_markup=back_to_kind(kind))


# --- подданный ---


@router.callback_query(F.data == CB_EVENTS_SUBJECT)
async def cb_subject(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    await callback.message.answer(**await render_subject(session, callback.from_user.id))


async def render_subject(session: AsyncSession, user_id: int) -> dict:
    emperor, rows = await ev.subject_events(session, user_id)
    if emperor is None:
        return {"text": t.SUBJECT_NO_EMPEROR, "reply_markup": subject_menu([])}
    lines = [
        t.SUBJECT_LINE.format(
            title=t.TITLES[row.kind], left=_left(row.ends_at),
            details=details(row.kind, row.params, slots=row.slots),
        )
        for row, _ in rows
    ]
    claimable = [(row.id, row.kind) for row, ok in rows if ok]
    return {"text": t.SUBJECT_SCREEN.format(lines="\n".join(lines) or t.SUBJECT_NONE), "reply_markup": subject_menu(claimable)}


@router.callback_query(F.data.startswith(CB_EVENTS_CLAIM_PREFIX))
async def cb_claim(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    raw = callback.data.removeprefix(CB_EVENTS_CLAIM_PREFIX)
    if not raw.isdigit():
        await callback.answer()
        return
    key = action_lock(callback.from_user.id, LOCK_ACTION_EMPIRE_EVENT)
    if not await redis.set(key, "1", nx=True, px=ACTION_LOCK_MS):
        await callback.answer(t.BUSY)
        return
    try:
        result = await ev.claim(session, callback.from_user.id, int(raw))
    except ev.EventGoneError:
        await session.rollback()
        await callback.answer(t.GONE_ALERT, show_alert=True)
        return
    except ev.AlreadyClaimedError:
        await session.rollback()
        await callback.answer(t.ALREADY_ALERT, show_alert=True)
        return
    except ev.EventEmptyError:
        await session.rollback()
        await callback.answer(t.EMPTY_ALERT, show_alert=True)
        return
    finally:
        await redis.delete(key)
    if result.rank:
        await callback.answer(t.CLAIMED_UNITS.format(amount=format_number(result.amount), rank=result.rank), show_alert=True)
    else:
        await callback.answer(t.CLAIMED_COINS.format(amount=format_number(result.amount)), show_alert=True)
