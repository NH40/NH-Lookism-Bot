"""Админка — Реферальные кампании: создание, ссылка, статистика, удаление."""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.admin import CB_ADMIN_SECTION_PREFIX, SECTION_REFERRAL
from bot.constant.admin.referral_admin import (
    CB_REF_DELETE_ASK_PREFIX,
    CB_REF_DELETE_PREFIX,
    CB_REF_NEW,
    CB_REF_VIEW_PREFIX,
)
from bot.constant.referral import REF_NAME_MAX_LEN
from bot.handlers.admin.common import guard, parse_id
from bot.keyboards.admin.referral_admin import back_to_list, delete_confirm_menu, detail_menu, list_menu
from bot.services import referral as referral_service
from bot.services.admin import roles
from bot.states.admin_referral import AdminReferralStates
from bot.texts.admin.referral_admin import (
    DELETE_ASK,
    DELETED_ALERT,
    DETAIL,
    LIST_EMPTY,
    LIST_HINT,
    LIST_TITLE,
    NAME_BAD,
    NEW_PROMPT,
    NOT_FOUND_ALERT,
)
from bot.utils.formatting import esc, format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="admin_referral")


async def _show_list(message, session: AsyncSession) -> None:
    rows = await referral_service.list_campaigns(session)
    text = LIST_TITLE + (LIST_EMPTY if not rows else "") + LIST_HINT
    items = [(link.id, f"{link.name} · {cnt}") for link, cnt in rows]
    await safe_edit_text(message, text, reply_markup=list_menu(items))


async def _show_detail(message, session: AsyncSession, bot: Bot, link_id: int) -> bool:
    link = await referral_service.get_campaign(session, link_id)
    if link is None:
        return False
    st = await referral_service.stats(session, link.id)
    username = (await bot.get_me()).username
    text = DETAIL.format(
        name=esc(link.name), link=referral_service.deep_link(username, link.code),
        came=format_number(st["came"]), playing=format_number(st["playing"]),
        donors=format_number(st["donors"]), donated=format_number(st["donated"]), bp=format_number(st["bp"]),
    )
    await safe_edit_text(message, text, reply_markup=detail_menu(link.id))
    return True


@router.callback_query(F.data == f"{CB_ADMIN_SECTION_PREFIX}{SECTION_REFERRAL}")
async def cb_section(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_REFERRAL):
        return
    await state.clear()
    await callback.answer()
    await _show_list(callback.message, session)


@router.callback_query(F.data == CB_REF_NEW)
async def cb_new(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_REFERRAL):
        return
    await state.set_state(AdminReferralStates.waiting_name)
    await callback.answer()
    await safe_edit_text(callback.message, NEW_PROMPT.format(limit=REF_NAME_MAX_LEN), reply_markup=back_to_list())


@router.message(StateFilter(AdminReferralStates.waiting_name), F.text, ~F.text.startswith("/"))
async def apply_name(message: Message, session: AsyncSession, state: FSMContext, bot: Bot) -> None:
    if not await roles.can(session, message.from_user.id, SECTION_REFERRAL):
        return
    name = message.text.strip()
    if not name or len(name) > REF_NAME_MAX_LEN:
        await message.answer(NAME_BAD.format(limit=REF_NAME_MAX_LEN), reply_markup=back_to_list())
        return
    link = await referral_service.create_campaign(session, message.from_user.id, name)
    await state.clear()
    username = (await bot.get_me()).username
    await message.answer(
        DETAIL.format(
            name=esc(link.name), link=referral_service.deep_link(username, link.code),
            came=0, playing=0, donors=0, donated=0, bp=0,
        ),
        reply_markup=detail_menu(link.id),
    )


@router.callback_query(F.data.startswith(CB_REF_VIEW_PREFIX))
async def cb_view(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    if not await guard(callback, session, SECTION_REFERRAL):
        return
    link_id = parse_id(callback.data, CB_REF_VIEW_PREFIX)
    if link_id is None or not await _show_detail(callback.message, session, bot, link_id):
        await callback.answer(NOT_FOUND_ALERT, show_alert=True)
        return
    await callback.answer()


@router.callback_query(F.data.startswith(CB_REF_DELETE_ASK_PREFIX))
async def cb_delete_ask(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_REFERRAL):
        return
    link_id = parse_id(callback.data, CB_REF_DELETE_ASK_PREFIX)
    link = await referral_service.get_campaign(session, link_id) if link_id else None
    if link is None:
        await callback.answer(NOT_FOUND_ALERT, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(callback.message, DELETE_ASK.format(name=esc(link.name)), reply_markup=delete_confirm_menu(link.id))


@router.callback_query(F.data.startswith(CB_REF_DELETE_PREFIX))
async def cb_delete(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_REFERRAL):
        return
    link_id = parse_id(callback.data, CB_REF_DELETE_PREFIX)
    if link_id is None or not await referral_service.delete_campaign(session, callback.from_user.id, link_id):
        await callback.answer(NOT_FOUND_ALERT, show_alert=True)
        return
    await callback.answer(DELETED_ALERT)
    await _show_list(callback.message, session)
