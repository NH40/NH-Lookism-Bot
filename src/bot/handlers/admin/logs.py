"""Админка — Журналы и аудит (хендлеры): действия админов, платежи, покупки, журнал игрока."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.admin import ADMIN_AUDIT_PAGE
from bot.config.settings import get_settings
from bot.constant.admin import (
    CB_ADMIN_PLAYER_LOG_PREFIX,
    CB_ADMIN_SECTION_PREFIX,
    SECTION_LOGS,
)
from bot.constant.admin.logs import (
    CB_LG_AUDIT_FILTER,
    CB_LG_AUDIT_PREFIX,
    CB_LG_BM,
    CB_LG_CLAN_PREFIX,
    CB_LG_PAY_PREFIX,
    CB_LG_PLAYER_PREFIX,
    PL_ACTIVITY,
    PL_AUDIT,
    PL_PAY,
)
from bot.handlers.admin.common import guard, parse_id
from bot.keyboards.admin import logs as kb
from bot.services.admin import audit, logs as svc, roles
from bot.texts.admin import logs as t
from bot.utils.safe_edit import safe_edit_text

router = Router(name="admin_logs")
_PER = ADMIN_AUDIT_PAGE


def _int(raw: str, default: int = 0) -> int:
    return int(raw) if raw.lstrip("-").isdigit() else default


@router.callback_query(F.data == f"{CB_ADMIN_SECTION_PREFIX}{SECTION_LOGS}")
async def cb_section(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_LOGS):
        return
    await callback.answer()
    await safe_edit_text(callback.message, t.MENU, reply_markup=kb.menu())


@router.callback_query(F.data.startswith(CB_LG_AUDIT_PREFIX))
async def cb_audit(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_LOGS):
        return
    await callback.answer()
    parts = callback.data.removeprefix(CB_LG_AUDIT_PREFIX).split(":")
    admin_id, page = _int(parts[0]), max(0, _int(parts[1] if len(parts) > 1 else "0"))
    rows, total = await audit.page(session, admin_id=admin_id or None, offset=page * _PER, limit=_PER)
    suffix = t.player_header(admin_id) if admin_id else ""
    await safe_edit_text(callback.message, t.audit_page(rows, total, page, _PER, suffix), reply_markup=kb.audit(admin_id, page, total, _PER))


@router.callback_query(F.data == CB_LG_AUDIT_FILTER)
async def cb_audit_filter(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_LOGS):
        return
    await callback.answer()
    staff = {uid: name for uid, name, _role in await roles.list_staff(session)}
    for uid in get_settings().admin_ids:
        staff.setdefault(uid, None)
    await safe_edit_text(callback.message, t.FILTER_TITLE, reply_markup=kb.audit_filter(sorted(staff.items())))


@router.callback_query(F.data.startswith(CB_LG_PAY_PREFIX))
async def cb_payments(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_LOGS):
        return
    await callback.answer()
    page = max(0, _int(callback.data.removeprefix(CB_LG_PAY_PREFIX)))
    rows, total = await svc.payments_page(session, offset=page * _PER, limit=_PER)
    await safe_edit_text(callback.message, t.payments_page(rows, total, page, _PER), reply_markup=kb.paged(CB_LG_PAY_PREFIX, page, total, _PER))


@router.callback_query(F.data.startswith(CB_LG_CLAN_PREFIX))
async def cb_clan(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_LOGS):
        return
    await callback.answer()
    page = max(0, _int(callback.data.removeprefix(CB_LG_CLAN_PREFIX)))
    rows, total = await svc.clan_purchases_page(session, offset=page * _PER, limit=_PER)
    await safe_edit_text(callback.message, t.clan_page(rows, total, page, _PER), reply_markup=kb.paged(CB_LG_CLAN_PREFIX, page, total, _PER))


@router.callback_query(F.data == CB_LG_BM)
async def cb_blackmarket(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_LOGS):
        return
    await callback.answer()
    await safe_edit_text(callback.message, t.blackmarket(await svc.blackmarket_summary(session)), reply_markup=kb.back_to_menu())


async def _render_player(callback: CallbackQuery, session: AsyncSession, uid: int, kind: str, page: int) -> None:
    offset = page * _PER
    if kind == PL_PAY:
        rows, total = await svc.payments_page(session, user_id=uid, offset=offset, limit=_PER)
        text = t.payments_page(rows, total, page, _PER, title=f"💳 <b>Платежи игрока</b>{t.player_header(uid)}")
    elif kind == PL_ACTIVITY:
        rows, total = await svc.activity_page(session, uid, offset=offset, limit=_PER)
        text = t.activity_page(rows, total, page, _PER)
    else:
        kind = PL_AUDIT
        rows, total = await audit.page(session, target_id=uid, offset=offset, limit=_PER)
        text = t.audit_page(rows, total, page, _PER, t.player_header(uid))
    await safe_edit_text(callback.message, text, reply_markup=kb.player(uid, kind, page, total, _PER))


@router.callback_query(F.data.startswith(CB_ADMIN_PLAYER_LOG_PREFIX))
async def cb_player_log(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_LOGS):
        return
    uid = parse_id(callback.data, CB_ADMIN_PLAYER_LOG_PREFIX)
    if uid is None:
        await callback.answer()
        return
    await callback.answer()
    await _render_player(callback, session, uid, PL_AUDIT, 0)


@router.callback_query(F.data.startswith(CB_LG_PLAYER_PREFIX))
async def cb_player_log_tab(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_LOGS):
        return
    await callback.answer()
    parts = callback.data.removeprefix(CB_LG_PLAYER_PREFIX).split(":")
    if len(parts) != 3 or not parts[0].isdigit():
        return
    await _render_player(callback, session, int(parts[0]), parts[1], max(0, _int(parts[2])))
