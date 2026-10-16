"""Админка — События карты (хендлеры): список, снятие, ручной запуск босса/учителей."""
from __future__ import annotations

import asyncio

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.constant.admin import CB_ADMIN_SECTION_PREFIX, SECTION_EVENTS
from bot.constant.admin import events_admin as C
from bot.constant.event import EVENT_BOSS, EVENT_SCHOOL_TEACHER, EVENT_TEACHER
from bot.handlers.admin.common import guard, parse_id
from bot.handlers.event import send_spawn_pushes
from bot.handlers.school import school_push_text
from bot.handlers.unique_technique import teacher_push_text
from bot.keyboards.admin import events_admin as K
from bot.services.admin import events_admin as svc
from bot.texts.admin import events_admin as T
from bot.texts.event import BOSS_NAMES
from bot.texts.school import SCHOOL_NAMES
from bot.texts.unique_technique import TECHNIQUE_NAMES
from bot.utils.formatting import esc, format_countdown
from bot.utils.safe_edit import safe_edit_text

router = Router(name="admin_events")
_BACKGROUND: set[asyncio.Task] = set()

_NAMES = {EVENT_BOSS: BOSS_NAMES, EVENT_TEACHER: TECHNIQUE_NAMES, EVENT_SCHOOL_TEACHER: SCHOOL_NAMES}


def _title(kind: str, code: str) -> str:
    return f"{T.KIND_ICONS.get(kind, '❔')} {_NAMES.get(kind, {}).get(code, code)}"


def _push_text(event) -> str | None:
    return teacher_push_text(event) or school_push_text(event)


async def _show_list(callback: CallbackQuery, session: AsyncSession) -> None:
    events = await svc.list_active(session)
    lines = [
        T.EVENT_LINE.format(
            icon=T.KIND_ICONS.get(e.kind, "❔"), title=esc(_NAMES.get(e.kind, {}).get(e.code, e.code)),
            left=format_countdown(e.left_seconds), clan=T.CLAN_TAG.format(clan_id=e.clan_id) if e.clan_id else "",
        )
        for e in events
    ]
    text = T.MENU_HEAD + ("\n".join(lines) + T.MENU_HINT if lines else T.MENU_EMPTY)
    await callback.answer()
    await safe_edit_text(callback.message, text, reply_markup=K.menu([(e.id, _title(e.kind, e.code)) for e in events]))


@router.callback_query(F.data.in_({f"{CB_ADMIN_SECTION_PREFIX}{SECTION_EVENTS}", C.CB_E_LIST}))
async def cb_section(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_EVENTS):
        return
    await _show_list(callback, session)


@router.callback_query(F.data.startswith(C.CB_E_VIEW_PREFIX))
async def cb_view(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_EVENTS):
        return
    eid = parse_id(callback.data, C.CB_E_VIEW_PREFIX)
    event = await svc.get_active(session, eid) if eid is not None else None
    if event is None:
        await callback.answer(T.ALERT_GONE, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(
        callback.message,
        T.EVENT_CARD.format(
            icon=T.KIND_ICONS.get(event.kind, "❔"), title=esc(_NAMES.get(event.kind, {}).get(event.code, event.code)),
            kind=T.KIND_NAMES.get(event.kind, event.kind), left=format_countdown(event.left_seconds), entries=event.entries,
            clan=f"\n{T.CLAN_TAG.format(clan_id=event.clan_id)}" if event.clan_id else "",
        ),
        reply_markup=K.event_card(event.id),
    )


@router.callback_query(F.data.startswith(C.CB_E_RM_ASK_PREFIX))
async def cb_rm_ask(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_EVENTS):
        return
    eid = parse_id(callback.data, C.CB_E_RM_ASK_PREFIX)
    event = await svc.get_active(session, eid) if eid is not None else None
    if event is None:
        await callback.answer(T.ALERT_GONE, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(
        callback.message, T.CONFIRM_REMOVE.format(title=esc(_NAMES.get(event.kind, {}).get(event.code, event.code))),
        reply_markup=K.confirm_remove(event.id),
    )


@router.callback_query(F.data.startswith(C.CB_E_RM_OK_PREFIX))
async def cb_rm_ok(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_EVENTS):
        return
    eid = parse_id(callback.data, C.CB_E_RM_OK_PREFIX)
    ok = await svc.remove(session, callback.from_user.id, eid) if eid is not None else False
    await callback.answer(T.DONE_REMOVED if ok else T.ALERT_GONE, show_alert=True)
    await _show_list(callback, session)


@router.callback_query(F.data == C.CB_E_SPAWN)
async def cb_spawn(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_EVENTS):
        return
    await callback.answer()
    await safe_edit_text(callback.message, T.SPAWN_KIND, reply_markup=K.spawn_kinds())


@router.callback_query(F.data.startswith(C.CB_E_KIND_PREFIX))
async def cb_kind(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_EVENTS):
        return
    key = callback.data.removeprefix(C.CB_E_KIND_PREFIX)
    kind = svc.KIND_BY_KEY.get(key)
    if kind is None:
        await callback.answer(T.ALERT_STALE, show_alert=True)
        return
    titles = [_NAMES[kind].get(code, code) for code in svc.CODES_BY_KIND[kind]]
    await callback.answer()
    await safe_edit_text(callback.message, T.SPAWN_CODE.format(kind=T.KIND_TITLES[key]), reply_markup=K.spawn_codes(key, titles))


def _parse_pick(data: str, prefix: str) -> tuple[str, int, str] | None:
    parts = data.removeprefix(prefix).split(":")
    if len(parts) < 2 or not parts[1].isdigit():
        return None
    return parts[0], int(parts[1]), (parts[2] if len(parts) > 2 else "")


@router.callback_query(F.data.startswith(C.CB_E_CODE_PREFIX))
async def cb_code(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_EVENTS):
        return
    pick = _parse_pick(callback.data, C.CB_E_CODE_PREFIX)
    kind = svc.KIND_BY_KEY.get(pick[0]) if pick else None
    codes = svc.CODES_BY_KIND.get(kind) if kind else None
    if not pick or codes is None or pick[1] >= len(codes):
        await callback.answer(T.ALERT_STALE, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(
        callback.message,
        T.SPAWN_PUSH.format(title=esc(_title(kind, codes[pick[1]])), left=format_countdown(svc.DURATION_BY_KIND[kind])),
        reply_markup=K.spawn_push(pick[0], pick[1]),
    )


@router.callback_query(F.data.startswith(C.CB_E_GO_PREFIX))
async def cb_go(
    callback: CallbackQuery, session: AsyncSession, bot: Bot, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    if not await guard(callback, session, SECTION_EVENTS):
        return
    pick = _parse_pick(callback.data, C.CB_E_GO_PREFIX)
    if pick is None:
        await callback.answer(T.ALERT_STALE, show_alert=True)
        return
    spawned = await svc.spawn_now(session, callback.from_user.id, pick[0], pick[1])
    if spawned is None:
        await callback.answer(T.ALERT_DUPLICATE, show_alert=True)
        return
    push = pick[2] == "1"
    if push:
        task = asyncio.create_task(send_spawn_pushes(bot, session_factory, [spawned], _push_text))
        _BACKGROUND.add(task)
        task.add_done_callback(_BACKGROUND.discard)
    await callback.answer(T.DONE_SPAWNED_PUSH if push else T.DONE_SPAWNED, show_alert=True)
    await _show_list(callback, session)
