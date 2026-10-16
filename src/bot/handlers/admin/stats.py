"""Админка — Статистика (хендлеры): игроки, донат, экономика, сервер."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.admin import CB_ADMIN_SECTION_PREFIX, SECTION_STATS
from bot.constant.admin.stats import CB_ST_DONATE, CB_ST_ECONOMY, CB_ST_OVERVIEW, CB_ST_SERVER
from bot.handlers.admin.common import guard
from bot.keyboards.admin import stats as kb
from bot.services.admin import stats as svc
from bot.texts.admin import stats as t
from bot.utils.safe_edit import safe_edit_text

router = Router(name="admin_stats")


@router.callback_query(F.data == f"{CB_ADMIN_SECTION_PREFIX}{SECTION_STATS}")
async def cb_section(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_STATS):
        return
    await callback.answer()
    await safe_edit_text(callback.message, t.MENU, reply_markup=kb.menu())


@router.callback_query(F.data.in_({CB_ST_OVERVIEW, CB_ST_DONATE, CB_ST_ECONOMY, CB_ST_SERVER}))
async def cb_sub(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if not await guard(callback, session, SECTION_STATS):
        return
    await callback.answer()
    data = callback.data
    if data == CB_ST_OVERVIEW:
        text = t.overview(await svc.overview(session))
    elif data == CB_ST_DONATE:
        text = t.donate(await svc.donate(session))
    elif data == CB_ST_ECONOMY:
        text = t.economy(await svc.economy(session))
    else:
        text = t.server(await svc.server(session, redis))
    await safe_edit_text(callback.message, text, reply_markup=kb.back())
