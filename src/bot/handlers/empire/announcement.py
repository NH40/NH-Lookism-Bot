"""Объявления императора: экран и отправка у императора, журнал у игрока (хендлеры)."""
from __future__ import annotations

import asyncio

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config.empire import EMPIRE_ANNOUNCE_MAX_CHARS
from bot.constant.admin.live_config import KEY_CD_EMPIRE_ANNOUNCE
from bot.constant.empire import CB_EMPIRE_ANNOUNCE, CB_EMPIRE_ANNOUNCE_SEND, CB_EMPIRE_ANNOUNCE_WRITE, CB_EMPIRE_LOG_PREFIX
from bot.keyboards.empire import announce_confirm_menu, announce_log_menu, announce_menu, back_to_announce_menu
from bot.services.admin.live_config import cooldown_seconds
from bot.services.empire import (
    AnnounceNoSubjectsError,
    AnnounceNotEmperorError,
    AnnounceOnCooldownError,
    AnnounceTextError,
    AnnounceView,
    announcement_log,
    clean_announcement,
    deliver_announcement,
    get_announce_view,
    publish_announcement,
)
from bot.states.empire import EmpireStates
from bot.texts.empire import (
    ANNOUNCE_BAD_TEXT,
    ANNOUNCE_COOLDOWN_ALERT,
    ANNOUNCE_COOLDOWN_LINE,
    ANNOUNCE_LOG_EMPTY,
    ANNOUNCE_LOG_ITEM,
    ANNOUNCE_LOG_SCREEN,
    ANNOUNCE_NO_SUBJECTS_ALERT,
    ANNOUNCE_PREVIEW,
    ANNOUNCE_PROMPT,
    ANNOUNCE_READY_LINE,
    ANNOUNCE_SCREEN,
    ANNOUNCE_SENT,
    ANNOUNCE_SENT_HEADER,
    ANNOUNCE_SENT_LINE,
    ANNOUNCE_STALE_ALERT,
    NOT_EMPEROR_ALERT,
)
from bot.utils.formatting import esc, format_countdown, format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="empire_announce")

_PREVIEW_CHARS = 120
_tasks: set[asyncio.Task] = set()


def _interval(seconds: int) -> str:
    if seconds and seconds % 3600 == 0:
        return f"{seconds // 3600} ч"
    return f"{seconds // 60} мин"


def _render(view: AnnounceView) -> str:
    sent = ""
    if view.sent:
        sent = ANNOUNCE_SENT_HEADER + "".join(
            ANNOUNCE_SENT_LINE.format(
                time=row.created_at.strftime("%d.%m %H:%M"),
                delivered=format_number(row.delivered),
                recipients=format_number(row.recipients),
                muted=format_number(row.muted),
                text=esc(row.text[:_PREVIEW_CHARS] + ("…" if len(row.text) > _PREVIEW_CHARS else "")),
            )
            for row in view.sent
        )
    status = (
        ANNOUNCE_COOLDOWN_LINE.format(countdown=format_countdown(view.cooldown_seconds))
        if view.cooldown_seconds
        else ANNOUNCE_READY_LINE
    )
    return ANNOUNCE_SCREEN.format(
        subjects=format_number(view.subjects),
        muted=format_number(view.muted),
        interval=_interval(cooldown_seconds(KEY_CD_EMPIRE_ANNOUNCE)),
        status=status,
        sent_block=sent,
    )


@router.callback_query(F.data == CB_EMPIRE_ANNOUNCE)
async def cb_announce_open(callback: CallbackQuery, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    await state.clear()
    try:
        view = await get_announce_view(session, redis, callback.from_user.id)
    except AnnounceNotEmperorError:
        await callback.answer(NOT_EMPEROR_ALERT, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(callback.message, _render(view), reply_markup=announce_menu())


@router.callback_query(F.data == CB_EMPIRE_ANNOUNCE_WRITE)
async def cb_announce_write(callback: CallbackQuery, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    try:
        view = await get_announce_view(session, redis, callback.from_user.id)
    except AnnounceNotEmperorError:
        await callback.answer(NOT_EMPEROR_ALERT, show_alert=True)
        return
    if view.cooldown_seconds:
        await callback.answer(ANNOUNCE_COOLDOWN_ALERT.format(countdown=format_countdown(view.cooldown_seconds)), show_alert=True)
        return
    if not view.subjects:
        await callback.answer(ANNOUNCE_NO_SUBJECTS_ALERT, show_alert=True)
        return
    await state.set_state(EmpireStates.waiting_announcement)
    await callback.answer()
    await safe_edit_text(
        callback.message, ANNOUNCE_PROMPT.format(limit=EMPIRE_ANNOUNCE_MAX_CHARS), reply_markup=back_to_announce_menu()
    )


@router.message(EmpireStates.waiting_announcement)
async def on_announce_text(message: Message, state: FSMContext) -> None:
    try:
        text = clean_announcement(message.text)
    except AnnounceTextError:
        await message.answer(ANNOUNCE_BAD_TEXT.format(limit=EMPIRE_ANNOUNCE_MAX_CHARS), reply_markup=back_to_announce_menu())
        return
    await state.update_data(announcement=text)
    await message.answer(ANNOUNCE_PREVIEW.format(text=esc(text)), reply_markup=announce_confirm_menu())


@router.callback_query(F.data == CB_EMPIRE_ANNOUNCE_SEND)
async def cb_announce_send(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    redis: Redis,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    text = (await state.get_data()).get("announcement")
    if not text:
        await callback.answer(ANNOUNCE_STALE_ALERT, show_alert=True)
        return
    try:
        published = await publish_announcement(session, redis, callback.from_user.id, text)
    except AnnounceNotEmperorError:
        await state.clear()
        await callback.answer(NOT_EMPEROR_ALERT, show_alert=True)
        return
    except AnnounceOnCooldownError as e:
        await state.clear()
        await callback.answer(ANNOUNCE_COOLDOWN_ALERT.format(countdown=format_countdown(e.retry_after_seconds)), show_alert=True)
        return
    except AnnounceNoSubjectsError:
        await state.clear()
        await callback.answer(ANNOUNCE_NO_SUBJECTS_ALERT, show_alert=True)
        return
    except AnnounceTextError:
        await callback.answer(ANNOUNCE_STALE_ALERT, show_alert=True)
        return
    await state.clear()
    await callback.answer()
    await safe_edit_text(
        callback.message,
        ANNOUNCE_SENT.format(
            count=format_number(len(published.recipient_ids)), muted=format_number(published.muted)
        ),
        reply_markup=back_to_announce_menu(),
    )
    task = asyncio.create_task(deliver_announcement(callback.bot, session_factory, published))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


@router.callback_query(F.data.startswith(CB_EMPIRE_LOG_PREFIX))
async def cb_announce_log(callback: CallbackQuery, session: AsyncSession) -> None:
    raw = callback.data.removeprefix(CB_EMPIRE_LOG_PREFIX)
    page = await announcement_log(session, callback.from_user.id, int(raw) if raw.isdigit() else 0)
    body = "".join(
        ANNOUNCE_LOG_ITEM.format(name=esc(row.emperor_name), time=row.created_at.strftime("%d.%m %H:%M"), text=esc(row.text))
        for row in page.items
    )
    await callback.answer()
    await safe_edit_text(
        callback.message,
        ANNOUNCE_LOG_SCREEN.format(items=body or ANNOUNCE_LOG_EMPTY),
        reply_markup=announce_log_menu(page.page, page.has_more),
    )
