"""Админка — Промокоды: создание одной строкой, список, детали, вкл/выкл, удаление."""
from __future__ import annotations

from datetime import timezone

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.admin import CB_ADMIN_SECTION_PREFIX, SECTION_PROMO
from bot.constant.admin.promo_admin import (
    CB_PROMO_DELETE_ASK_PREFIX,
    CB_PROMO_DELETE_PREFIX,
    CB_PROMO_NEW,
    CB_PROMO_TOGGLE_PREFIX,
    CB_PROMO_VIEW_PREFIX,
)
from bot.constant.promo import PROMO_LIST_LIMIT
from bot.constant.resource import RESOURCES
from bot.db.models.promo import PromoCode
from bot.handlers.admin.common import guard, parse_id
from bot.keyboards.admin.promo_admin import back_to_list, delete_confirm_menu, detail_menu, list_menu
from bot.services import promo as promo_service
from bot.services.admin import roles
from bot.states.admin_promo import AdminPromoStates
from bot.texts.admin.promo_admin import (
    CODE_TAKEN,
    CREATE_PROMPT,
    CREATED,
    DELETE_ASK,
    DELETED_ALERT,
    DETAIL,
    FORMAT_ERROR,
    LIST_EMPTY,
    LIST_HINT,
    LIST_TITLE,
    NOT_FOUND_ALERT,
    STATUS_ALIVE,
    STATUS_DEAD,
    STATUS_OFF,
)
from bot.texts.resource import amount_label
from bot.utils.formatting import esc, format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="admin_promo")


def _reward_text(reward: dict) -> str:
    return " ".join(f"{'+' if v > 0 else '−'}{amount_label(k, abs(int(v)))}" for k, v in reward.items())


def _status(promo: PromoCode) -> str:
    if not promo.is_active:
        return STATUS_OFF
    return STATUS_ALIVE if promo_service.is_alive(promo) else STATUS_DEAD


async def _show_list(message, session: AsyncSession) -> None:
    promos = await promo_service.list_recent(session)
    text = LIST_TITLE + (LIST_EMPTY if not promos else "") + LIST_HINT.format(limit=PROMO_LIST_LIMIT)
    items = []
    for p in promos:
        icon = "✅" if promo_service.is_alive(p) else "❌"
        limit = f"/{p.max_uses}" if p.max_uses is not None else ""
        items.append((p.id, f"{icon} {p.code} · {p.used_count}{limit}"))
    await safe_edit_text(message, text, reply_markup=list_menu(items))


async def _show_detail(message, session: AsyncSession, promo_id: int) -> bool:
    promo = await promo_service.get(session, promo_id)
    if promo is None:
        return False
    expires = promo.expires_at.astimezone(timezone.utc).strftime("%d.%m.%Y %H:%M UTC") if promo.expires_at else "без срока"
    users = f"🔒 Только: {esc(', '.join('@' + u for u in promo.allowed_usernames))}\n" if promo.allowed_usernames else ""
    text = DETAIL.format(
        code=esc(promo.code), status=_status(promo), reward=_reward_text(promo.reward),
        used=format_number(promo.used_count),
        limit=f" / {format_number(promo.max_uses)}" if promo.max_uses is not None else "",
        expires=expires, users=users,
    )
    await safe_edit_text(message, text, reply_markup=detail_menu(promo.id, promo.is_active))
    return True


@router.callback_query(F.data == f"{CB_ADMIN_SECTION_PREFIX}{SECTION_PROMO}")
async def cb_section(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_PROMO):
        return
    await state.clear()
    await callback.answer()
    await _show_list(callback.message, session)


@router.callback_query(F.data == CB_PROMO_NEW)
async def cb_new(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_PROMO):
        return
    await state.set_state(AdminPromoStates.waiting_create)
    await callback.answer()
    await safe_edit_text(
        callback.message, CREATE_PROMPT.format(resources=" ".join(RESOURCES)), reply_markup=back_to_list()
    )


@router.message(StateFilter(AdminPromoStates.waiting_create), F.text, ~F.text.startswith("/"))
async def apply_create(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not await roles.can(session, message.from_user.id, SECTION_PROMO):
        return
    try:
        draft = promo_service.parse_create(message.text)
    except promo_service.PromoFormatError:
        await message.answer(FORMAT_ERROR, reply_markup=back_to_list())
        return
    try:
        promo = await promo_service.create(session, message.from_user.id, draft)
    except promo_service.PromoCodeTakenError:
        await message.answer(CODE_TAKEN, reply_markup=back_to_list())
        return
    await state.clear()
    await message.answer(CREATED.format(code=esc(promo.code), reward=_reward_text(promo.reward)), reply_markup=back_to_list())


@router.callback_query(F.data.startswith(CB_PROMO_VIEW_PREFIX))
async def cb_view(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_PROMO):
        return
    promo_id = parse_id(callback.data, CB_PROMO_VIEW_PREFIX)
    if promo_id is None or not await _show_detail(callback.message, session, promo_id):
        await callback.answer(NOT_FOUND_ALERT, show_alert=True)
        return
    await callback.answer()


@router.callback_query(F.data.startswith(CB_PROMO_TOGGLE_PREFIX))
async def cb_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_PROMO):
        return
    promo_id = parse_id(callback.data, CB_PROMO_TOGGLE_PREFIX)
    promo = await promo_service.get(session, promo_id) if promo_id else None
    if promo is None:
        await callback.answer(NOT_FOUND_ALERT, show_alert=True)
        return
    await promo_service.set_active(session, callback.from_user.id, promo.id, not promo.is_active)
    await session.refresh(promo)
    await callback.answer()
    await _show_detail(callback.message, session, promo.id)


@router.callback_query(F.data.startswith(CB_PROMO_DELETE_ASK_PREFIX))
async def cb_delete_ask(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_PROMO):
        return
    promo_id = parse_id(callback.data, CB_PROMO_DELETE_ASK_PREFIX)
    promo = await promo_service.get(session, promo_id) if promo_id else None
    if promo is None:
        await callback.answer(NOT_FOUND_ALERT, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(callback.message, DELETE_ASK.format(code=esc(promo.code)), reply_markup=delete_confirm_menu(promo.id))


@router.callback_query(F.data.startswith(CB_PROMO_DELETE_PREFIX))
async def cb_delete(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_PROMO):
        return
    promo_id = parse_id(callback.data, CB_PROMO_DELETE_PREFIX)
    if promo_id is None or not await promo_service.delete(session, callback.from_user.id, promo_id):
        await callback.answer(NOT_FOUND_ALERT, show_alert=True)
        return
    await callback.answer(DELETED_ALERT)
    await _show_list(callback.message, session)
