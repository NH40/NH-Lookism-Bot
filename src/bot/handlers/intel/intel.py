"""Разведка — отчёт о игроке по юзернейму и метки (хендлеры).

Вход — «🔍 Разведка» и «📍 Метки» на экране «📈 Развитие»; кнопки видны, только если
системы развития их открыли (гении хакинга/наблюдения, путь Сенсорики). Права
перепроверяет сервис на каждом действии.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from redis.asyncio import Redis

from bot.services.intel import UnmarkableError
from bot.texts.intel import UNMARKABLE_ALERT
from bot.constant.intel import CB_INTEL_REPORTS
from bot.constant.position_skill import CB_SCOUT_PREFIX, CB_SCOUT_REPORT_PREFIX
from bot.constant.settings import NOTIFY_SABOTAGE
from bot.db.repositories.activity import list_marks
from bot.db.repositories.user import get_by_id
from bot.keyboards.intel import reports_menu
from bot.services.build import get_build
from bot.services.intel import (
    NoScoutError,
    ScoutTargetError,
    get_scout_report,
    list_scout_reports,
    scout,
    scout_ago,
    scout_levels,
    scout_report_lines,
)
from bot.services.settings import notify_player
from bot.texts.intel import (
    BTN_REPORT_ROW,
    NO_REPORTS,
    NO_SCOUT_ALERT,
    PUSH_SCOUTED,
    PUSH_SCOUTED_BY,
    REPORTS_SCREEN,
    SCOUT_LINE,
    SCOUT_PROMPT,
    SCOUT_REPORT,
    SCOUT_TRAP,
)
from bot.constant.intel import CB_INTEL_MARK_PREFIX, CB_INTEL_MARKS, CB_INTEL_OPEN
from bot.keyboards.intel import back_menu, report_menu
from bot.services.intel import (
    IntelReport,
    MarksFullError,
    get_access,
    get_marks_feed,
    toggle_mark,
)
from bot.states.intel import IntelStates
from bot.texts.bloodline import BLOODLINE_NAMES
from bot.texts.genius import GENIUS_NAMES
from bot.texts.intel import (
    BUILD_HEADER,
    BUILD_LINE,
    BUILD_NONE,
    CAMP_ATTACK,
    CAMP_DEFENSE,
    CAMP_LINE,
    CAMP_TOP_LINE,
    HIDDEN,
    LOG_LINE,
    LOGS_EMPTY,
    LOGS_HEADER,
    MARK_BLOCK,
    MARK_HIDDEN,
    MARKED_ALERT,
    MARKS_EMPTY,
    MARKS_FULL_ALERT,
    MARKS_SCREEN,
    NO_ACCESS_ALERT,
    NO_SCOUT,
    NOT_FOUND,
    REPORT,
    SYSTEM_BLOODLINE,
    SYSTEM_GENIUS,
    SYSTEM_PATH,
    SYSTEM_TECHNIQUE,
    UNMARKED_ALERT,
)
from bot.texts.unique_path import PATH_NAMES
from bot.texts.unique_technique import TECHNIQUE_NAMES
from bot.utils.formatting import esc, format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="intel")


def _name(username: str | None, display_name: str | None) -> str:
    return f"@{esc(username)}" if username else esc(display_name or "—")


def _when(dt) -> str:
    return dt.strftime("%d.%m %H:%M")


def render_report(report: IntelReport) -> str:
    lines: list[str] = []
    if report.stealth_hidden:
        lines.append(HIDDEN)
    else:
        if report.attack is None:
            lines.append(NO_SCOUT)
        for icon, camp_name, camp in (("⚔️", CAMP_ATTACK, report.attack), ("🛡", CAMP_DEFENSE, report.defense)):
            if camp is None:
                continue
            lines.append(CAMP_LINE.format(icon=icon, camp=camp_name, power=format_number(camp.power), quantity=format_number(camp.quantity)))
            lines.extend(CAMP_TOP_LINE.format(label=esc(label), count=format_number(count)) for label, count in camp.top)
        if report.build is not None:
            b = report.build
            lines.append(BUILD_HEADER)
            parts = [
                (SYSTEM_BLOODLINE, BLOODLINE_NAMES.get(b.bloodline), b.bloodline_level),
                (SYSTEM_PATH, PATH_NAMES.get(b.path), b.path_level),
                (SYSTEM_TECHNIQUE, TECHNIQUE_NAMES.get(b.technique), b.technique_level),
                (SYSTEM_GENIUS, GENIUS_NAMES.get(b.genius), b.genius_level),
            ]
            shown = [BUILD_LINE.format(system=s, name=n, level=lv) for s, n, lv in parts if n]
            lines.extend(shown or [BUILD_NONE])
        if report.logs:
            lines.append(LOGS_HEADER)
            lines.extend(LOG_LINE.format(when=_when(t), text=esc(x)) for t, x in report.entries)
            if not report.entries:
                lines.append(LOGS_EMPTY)
    return REPORT.format(name=_name(report.username, report.display_name), body="\n".join(lines))


@router.callback_query(F.data == CB_INTEL_OPEN)
async def cb_intel_open(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    access = await get_access(session, callback.from_user.id)
    fields = await scout_levels(session, callback.from_user.id)
    if not fields and not access.marks:
        await callback.answer(NO_SCOUT_ALERT, show_alert=True)
        return
    await state.set_state(IntelStates.waiting_username)
    await callback.answer()
    await safe_edit_text(callback.message, SCOUT_PROMPT.format(fields=len(fields), marks=access.marks), reply_markup=back_menu())


@router.message(IntelStates.waiting_username)
async def on_intel_username(message: Message, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    try:
        result = await scout(session, redis, message.from_user.id, username=message.text or "")
    except NoScoutError:
        await state.clear()
        await message.answer(NO_SCOUT_ALERT)
        return
    except ScoutTargetError:
        await message.answer(NOT_FOUND, reply_markup=back_menu())
        return
    await state.clear()
    text, markup = await _render_scout(session, message.from_user.id, result.target_id, result.payload, result.created_at)
    await message.answer(text + (SCOUT_TRAP.format(count=format_number(result.trap_lost)) if result.trap_lost else ""), reply_markup=markup)
    await _notify_scouted(message.bot, session, result, message.from_user.id)


async def _render_scout(session: AsyncSession, viewer_id: int, target_id: int, payload: dict, created_at):
    """Сохранённый отчёт + кнопки (разведать снова, метка, саботаж помеченного)."""
    lines = [SCOUT_LINE.format(label=esc(label), value=esc(value)) for _f, label, value in scout_report_lines(payload)]
    text = SCOUT_REPORT.format(name=esc(payload.get("_target", "—")), ago=scout_ago(created_at), body="\n".join(lines) or "—")
    access = await get_access(session, viewer_id)
    marks = await list_marks(session, viewer_id)
    flags = (await get_build(session, viewer_id)).flags
    marked = target_id in marks
    return text, report_menu(target_id, can_mark=access.marks > 0, marked=marked, can_sabotage=marked and "sabotage_marked" in flags)


async def _notify_scouted(bot, session: AsyncSession, result, viewer_id: int) -> None:
    """Безопасность цели: «Двойной агент» — знает, кто; «Тревога» — знает, что разведали."""
    if result.notify_target is None:
        return
    if result.notify_target == "double_agent":
        viewer = await get_by_id(session, viewer_id)
        name = viewer.display_name or (f"@{viewer.username}" if viewer and viewer.username else "—") if viewer else "—"
        text = PUSH_SCOUTED_BY.format(name=esc(name))
    else:
        text = PUSH_SCOUTED
    await notify_player(bot, session, result.target_id, NOTIFY_SABOTAGE, text)


@router.callback_query(F.data.startswith(CB_SCOUT_PREFIX))
async def cb_scout_again(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    raw = callback.data.removeprefix(CB_SCOUT_PREFIX)
    if not raw.isdigit():
        await callback.answer()
        return
    try:
        result = await scout(session, redis, callback.from_user.id, target_id=int(raw))
    except NoScoutError:
        await callback.answer(NO_SCOUT_ALERT, show_alert=True)
        return
    except ScoutTargetError:
        await callback.answer(NOT_FOUND, show_alert=True)
        return
    await callback.answer()
    text, markup = await _render_scout(session, callback.from_user.id, result.target_id, result.payload, result.created_at)
    await safe_edit_text(callback.message, text + (SCOUT_TRAP.format(count=format_number(result.trap_lost)) if result.trap_lost else ""), reply_markup=markup)
    await _notify_scouted(callback.bot, session, result, callback.from_user.id)


@router.callback_query(F.data.startswith(CB_SCOUT_REPORT_PREFIX))
async def cb_scout_report(callback: CallbackQuery, session: AsyncSession) -> None:
    raw = callback.data.removeprefix(CB_SCOUT_REPORT_PREFIX)
    row = await get_scout_report(session, callback.from_user.id, int(raw)) if raw.isdigit() else None
    if row is None:
        await callback.answer(NO_REPORTS, show_alert=True)
        return
    await callback.answer()
    text, markup = await _render_scout(session, callback.from_user.id, row.target_id, row.payload, row.created_at)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data == CB_INTEL_REPORTS)
async def cb_scout_reports(callback: CallbackQuery, session: AsyncSession) -> None:
    rows = await list_scout_reports(session, callback.from_user.id)
    await callback.answer()
    if not rows:
        await safe_edit_text(callback.message, NO_REPORTS, reply_markup=back_menu())
        return
    buttons = [(r.target_id, BTN_REPORT_ROW.format(name=r.payload.get("_target", "—"), ago=scout_ago(r.created_at))) for r in rows]
    await safe_edit_text(callback.message, REPORTS_SCREEN, reply_markup=reports_menu(buttons))


@router.callback_query(F.data.startswith(CB_INTEL_MARK_PREFIX))
async def cb_intel_mark(callback: CallbackQuery, session: AsyncSession) -> None:
    raw = callback.data.removeprefix(CB_INTEL_MARK_PREFIX)
    if not raw.isdigit():
        await callback.answer()
        return
    target_id = int(raw)
    # Popup-тексты — без HTML.
    try:
        marked = await toggle_mark(session, callback.from_user.id, target_id)
    except UnmarkableError:
        await callback.answer(UNMARKABLE_ALERT, show_alert=True)
        return
    except MarksFullError as exc:
        await callback.answer(MARKS_FULL_ALERT.format(limit=exc.limit), show_alert=True)
        return
    await callback.answer(MARKED_ALERT if marked else UNMARKED_ALERT)
    await callback.message.edit_reply_markup(reply_markup=report_menu(target_id, can_mark=True, marked=marked))


@router.callback_query(F.data == CB_INTEL_MARKS)
async def cb_intel_marks(callback: CallbackQuery, session: AsyncSession) -> None:
    limit, feeds = await get_marks_feed(session, callback.from_user.id)
    if not limit and not feeds:
        await callback.answer(NO_ACCESS_ALERT, show_alert=True)
        return
    await callback.answer()
    blocks = []
    for f in feeds:
        entries = [MARK_HIDDEN] if f.hidden else [LOG_LINE.format(when=_when(t), text=esc(x)) for t, x in f.entries] or [LOGS_EMPTY]
        blocks.append(MARK_BLOCK.format(name=_name(f.username, f.display_name), entries="\n".join(entries)))
    body = "\n\n".join(blocks) if blocks else MARKS_EMPTY
    await safe_edit_text(callback.message, MARKS_SCREEN.format(used=len(feeds), limit=limit, body=body), reply_markup=back_menu())
