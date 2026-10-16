"""Админка — Патч и вайп (хендлеры). Только супер-админ. Подтверждение — два нажатия за 30 с."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.settings import get_settings
from bot.constant.admin import CB_ADMIN_SECTION_PREFIX, SECTION_PATCH
from bot.constant.admin.live_config import (
    AUDIT_PATCH,
    AUDIT_WIPE,
    CB_PATCH_PATCH_INFO,
    CB_PATCH_PATCH_STEP1,
    CB_PATCH_PATCH_STEP2,
    CB_PATCH_WIPE_INFO,
    CB_PATCH_WIPE_STEP1,
    CB_PATCH_WIPE_STEP2,
    CONFIRM_KIND_PATCH,
    CONFIRM_KIND_WIPE,
)
from bot.handlers.admin.common import guard
from bot.keyboards.admin.patch import back_menu, menu, step1_menu, step2_menu
from bot.services.admin import audit
from bot.services.admin import live_config, patch as patch_service
from bot.services import top as top_service
from bot.constant.top import PAYOUT_KEY_PATCH
from bot.texts.admin.patch import (
    ALREADY_RUNNING,
    EXPIRED_ALERT,
    MENU,
    PATCH_DONE,
    PATCH_FAILED,
    PATCH_INFO,
    PATCH_PROGRESS,
    PATCH_STARTED,
    STEP2_PROMPT,
    WIPE_DONE,
    WIPE_INFO,
    WIPE_NOTIFY,
)
from bot.utils.formatting import format_number
from bot.utils.notify import notify
from bot.utils.safe_edit import safe_edit_text

router = Router(name="admin_patch")
_tasks: set[asyncio.Task] = set()  # ссылки на фоновые задачи (иначе GC может собрать)
_PROGRESS_EVERY = 1000


@router.callback_query(F.data == f"{CB_ADMIN_SECTION_PREFIX}{SECTION_PATCH}")
async def cb_section(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_PATCH):
        return
    await callback.answer()
    await safe_edit_text(callback.message, MENU, reply_markup=menu())


@router.callback_query(F.data == CB_PATCH_PATCH_INFO)
async def cb_patch_info(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_PATCH):
        return
    await callback.answer()
    text = PATCH_INFO.format(
        coins=format_number(live_config.get("starting_nh_coins")), tickets=format_number(live_config.get("starting_tickets"))
    )
    await safe_edit_text(callback.message, text, reply_markup=step1_menu(False))


@router.callback_query(F.data == CB_PATCH_WIPE_INFO)
async def cb_wipe_info(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_PATCH):
        return
    await callback.answer()
    await safe_edit_text(callback.message, WIPE_INFO, reply_markup=step1_menu(True))


async def _step1(callback: CallbackQuery, session: AsyncSession, redis: Redis, kind: str, wipe: bool) -> None:
    if not await guard(callback, session, SECTION_PATCH):
        return
    await patch_service.arm(redis, kind, callback.from_user.id)
    await callback.answer()
    await safe_edit_text(callback.message, STEP2_PROMPT, reply_markup=step2_menu(wipe))


@router.callback_query(F.data == CB_PATCH_PATCH_STEP1)
async def cb_patch_step1(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    await _step1(callback, session, redis, CONFIRM_KIND_PATCH, False)


@router.callback_query(F.data == CB_PATCH_WIPE_STEP1)
async def cb_wipe_step1(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    await _step1(callback, session, redis, CONFIRM_KIND_WIPE, True)


@router.callback_query(F.data == CB_PATCH_PATCH_STEP2)
async def cb_patch_step2(callback: CallbackQuery, session: AsyncSession, redis: Redis, bot, session_factory) -> None:
    if not await guard(callback, session, SECTION_PATCH):
        return
    if not await patch_service.take(redis, CONFIRM_KIND_PATCH, callback.from_user.id):
        await callback.answer(EXPIRED_ALERT, show_alert=True)
        return
    if patch_service.is_running():
        await callback.answer(ALREADY_RUNNING, show_alert=True)
        return
    admin_id = callback.from_user.id
    await audit.log(session, admin_id, AUDIT_PATCH, None, {})
    await session.commit()
    await callback.answer()
    await safe_edit_text(callback.message, PATCH_STARTED, reply_markup=back_menu())
    message = callback.message

    async def progress(done: int) -> None:
        if done % _PROGRESS_EVERY == 0:  # раз в 1000 игроков (пачки по 200)
            await safe_edit_text(message, PATCH_PROGRESS.format(done=format_number(done)), reply_markup=back_menu())

    async def job() -> None:
        try:
            # Вайп = конец сезона: победителей снимаем ДО сброса (патч обнулит армии), а
            # начисляем ПОСЛЕ — иначе сброс съел бы NHCoin и тикеты награды.
            winners = await top_service.snapshot_winners(session_factory)
            done = await patch_service.run_patch(session_factory, progress)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            await top_service.award(bot, session_factory, PAYOUT_KEY_PATCH.format(stamp=stamp), winners)
            await notify(bot, admin_id, PATCH_DONE.format(done=format_number(done)))
        except Exception as exc:  # отчёт инициатору, остальное — в лог
            await notify(bot, admin_id, PATCH_FAILED.format(done="?", error=type(exc).__name__))
            raise

    task = asyncio.create_task(job())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


@router.callback_query(F.data == CB_PATCH_WIPE_STEP2)
async def cb_wipe_step2(callback: CallbackQuery, session: AsyncSession, redis: Redis, bot, session_factory) -> None:
    if not await guard(callback, session, SECTION_PATCH):
        return
    if not await patch_service.take(redis, CONFIRM_KIND_WIPE, callback.from_user.id):
        await callback.answer(EXPIRED_ALERT, show_alert=True)
        return
    admin_id = callback.from_user.id
    tables = await patch_service.wipe_database(session)
    # Журнал аудита тоже очищен вайпом — пишем запись о самом вайпе уже после него.
    await audit.log(session, admin_id, AUDIT_WIPE, None, {"tables": len(tables)})
    await session.commit()
    await live_config.load(session_factory)  # game_settings очищена — кэш в память заново
    await callback.answer()
    await safe_edit_text(callback.message, WIPE_DONE.format(n=len(tables)), reply_markup=back_menu())
    for uid in get_settings().admin_ids:
        await notify(bot, uid, WIPE_NOTIFY.format(admin=admin_id))
