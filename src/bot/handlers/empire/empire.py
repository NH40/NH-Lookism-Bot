"""Император — экран «👑 Империя»: казна, общий и персональный налог (хендлеры).

Вход — кнопка «👑 Империя» в меню профиля (видна только императору). Права перепроверяет
сервис (`NotEmperorError`) на каждом действии, не только видимость кнопки — императора
могли свергнуть, пока экран висел в чате.
"""
from __future__ import annotations

from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.empire import (
    CB_EMPIRE_OPEN,
    CB_EMPIRE_PERSONAL,
    CB_EMPIRE_PERSONAL_RATE_PREFIX,
    CB_EMPIRE_RATE_PREFIX,
    EMPIRE_RATE_RESET,
)
from bot.db.repositories.empire import EmpireStats
from bot.keyboards.empire import back_to_empire_menu, empire_menu, personal_rate_menu
from bot.services.empire import (
    InvalidRateError,
    NotEmperorError,
    SubjectNotFoundError,
    find_subject,
    get_incoming_war,
    get_overview,
    set_global_rate,
    set_personal_rate,
)
from bot.services.gang import get_gang
from bot.states.empire import EmpireStates
from bot.texts.empire import (
    EMPIRE_SCREEN,
    INVALID_RATE_ALERT,
    NOT_EMPEROR_ALERT,
    OVERRIDE_LINE,
    OVERRIDES_HEADER,
    OVERRIDES_MORE,
    PERSONAL_NOTE_GLOBAL,
    PERSONAL_NOTE_OWN,
    PERSONAL_PICK,
    PERSONAL_PROMPT,
    PERSONAL_RESET_ALERT,
    PERSONAL_SET_ALERT,
    INCOMING_WAR_LINE,
    RATE_SET_ALERT,
    SABOTAGE_LINE,
    SUBJECT_GONE_ALERT,
    SUBJECT_NOT_FOUND,
)
from bot.utils.formatting import esc, format_countdown, format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="empire_rates")


async def get_gang_label(session: AsyncSession, user_id: int) -> str:
    gang = await get_gang(session, user_id)
    return gang.name if gang else "—"


def _name(username: str | None, display_name: str | None) -> str:
    return f"@{esc(username)}" if username else esc(display_name or "—")


def render_empire(stats: EmpireStats, incoming=None, incoming_label: str = ""):
    block = ""
    if stats.overrides_total:
        block = OVERRIDES_HEADER.format(total=stats.overrides_total) + "".join(
            OVERRIDE_LINE.format(name=_name(username, name), percent=percent)
            for username, name, percent in stats.overrides
        )
        if stats.overrides_total > len(stats.overrides):
            block += OVERRIDES_MORE.format(more=stats.overrides_total - len(stats.overrides))
    text = EMPIRE_SCREEN.format(
        cities=stats.cities,
        players=format_number(stats.players),
        coins=format_number(stats.nh_coins),
        collected=format_number(stats.collected),
        rate=stats.tax_percent,
        overrides_block=block,
        incoming_line=(
            INCOMING_WAR_LINE.format(
                attacker=esc(incoming_label),
                countdown=format_countdown(
                    max(0, int((incoming.expires_at - datetime.now(timezone.utc)).total_seconds()))
                ),
            )
            if incoming is not None
            else ""
        ),
        sabotage_line=(
            SABOTAGE_LINE.format(total=stats.sabotage_total, success=stats.sabotage_success)
            if stats.sabotage_total
            else ""
        ),
    )
    return text, empire_menu(stats.tax_percent, incoming.id if incoming is not None else None)


async def _overview(session: AsyncSession, user_id: int, stats: EmpireStats | None = None):
    """Экран империи целиком: сводка + висящая против императора война (если есть)."""
    stats = stats or await get_overview(session, user_id)
    incoming = await get_incoming_war(session, user_id)
    label = await get_gang_label(session, incoming.attacker_id) if incoming is not None else ""
    return render_empire(stats, incoming, label)


@router.callback_query(F.data == CB_EMPIRE_OPEN)
async def cb_empire_open(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    # Кнопка «К империи» жмётся и из ожидания юзернейма — не оставляем висящее состояние.
    await state.clear()
    try:
        stats = await get_overview(session, callback.from_user.id)
    except NotEmperorError:
        await callback.answer(NOT_EMPEROR_ALERT, show_alert=True)
        return
    await callback.answer()
    text, markup = await _overview(session, callback.from_user.id, stats)
    await callback.message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_EMPIRE_RATE_PREFIX))
async def cb_empire_rate(callback: CallbackQuery, session: AsyncSession) -> None:
    raw = callback.data.removeprefix(CB_EMPIRE_RATE_PREFIX)
    if not raw.isdigit():
        await callback.answer()
        return
    percent = int(raw)
    try:
        await set_global_rate(session, callback.from_user.id, percent)
    except NotEmperorError:
        await callback.answer(NOT_EMPEROR_ALERT, show_alert=True)
        return
    except InvalidRateError:
        await callback.answer(INVALID_RATE_ALERT, show_alert=True)
        return
    await callback.answer(RATE_SET_ALERT.format(percent=percent))
    text, markup = await _overview(session, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data == CB_EMPIRE_PERSONAL)
async def cb_empire_personal(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    try:
        await get_overview(session, callback.from_user.id)
    except NotEmperorError:
        await callback.answer(NOT_EMPEROR_ALERT, show_alert=True)
        return
    await state.set_state(EmpireStates.waiting_username)
    await callback.answer()
    await safe_edit_text(callback.message, PERSONAL_PROMPT, reply_markup=back_to_empire_menu())


@router.message(EmpireStates.waiting_username)
async def on_personal_username(message: Message, state: FSMContext, session: AsyncSession) -> None:
    username = (message.text or "").strip()
    try:
        found = await find_subject(session, message.from_user.id, username)
    except NotEmperorError:
        await state.clear()
        await message.answer(NOT_EMPEROR_ALERT)
        return
    except SubjectNotFoundError:
        await message.answer(SUBJECT_NOT_FOUND, reply_markup=back_to_empire_menu())
        return
    await state.clear()
    subject = found.subject
    await message.answer(
        PERSONAL_PICK.format(
            name=_name(subject.username, subject.display_name),
            percent=found.percent,
            note=PERSONAL_NOTE_OWN if found.has_override else PERSONAL_NOTE_GLOBAL,
        ),
        reply_markup=personal_rate_menu(subject.user_id, found.percent, has_override=found.has_override),
    )


@router.callback_query(F.data.startswith(CB_EMPIRE_PERSONAL_RATE_PREFIX))
async def cb_empire_personal_rate(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        raw_subject, raw_rate = callback.data.removeprefix(CB_EMPIRE_PERSONAL_RATE_PREFIX).split(":", 1)
        subject_id = int(raw_subject)
        percent = None if raw_rate == EMPIRE_RATE_RESET else int(raw_rate)
    except ValueError:
        await callback.answer()
        return
    try:
        await set_personal_rate(session, callback.from_user.id, subject_id, percent)
    except NotEmperorError:
        await callback.answer(NOT_EMPEROR_ALERT, show_alert=True)
        return
    except InvalidRateError:
        await callback.answer(INVALID_RATE_ALERT, show_alert=True)
        return
    except SubjectNotFoundError:
        await callback.answer(SUBJECT_GONE_ALERT, show_alert=True)
        return
    await callback.answer(
        PERSONAL_RESET_ALERT if percent is None else PERSONAL_SET_ALERT.format(percent=percent)
    )
    text, markup = await _overview(session, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)
