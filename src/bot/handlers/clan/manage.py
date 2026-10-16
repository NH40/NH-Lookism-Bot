"""Кланы — управление (хендлеры): заявки, приглашения, ранги, передача, роспуск, исключение,
редактирование и аватарка. Права перепроверяет сервис на каждом шаге (как в UAP)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.clan import CLAN_DESCRIPTION_MAX, CLAN_NAME_MAX, CLAN_NAME_MIN
from bot.constant.clan import (
    CB_CLAN_ACCEPT_PREFIX,
    CB_CLAN_DELETE,
    CB_CLAN_DELETE_CONFIRM,
    CB_CLAN_EDIT,
    CB_CLAN_EDIT_DESCRIPTION,
    CB_CLAN_EDIT_IMAGE,
    CB_CLAN_EDIT_NAME,
    CB_CLAN_INVITE,
    CB_CLAN_KICK,
    CB_CLAN_KICK_PREFIX,
    CB_CLAN_RANK_PREFIX,
    CB_CLAN_RANKS,
    CB_CLAN_REJECT_PREFIX,
    CB_CLAN_REQUESTS,
    CB_CLAN_TRANSFER,
    CB_CLAN_TRANSFER_PREFIX,
    MANAGER_RANKS,
    RANK_OWNER,
)
from bot.constant.settings import NOTIFY_CLAN
from bot.db.repositories import clan as clan_repo
from bot.handlers.clan.clan import error_text, render_clan, send_screen, valid_name
from bot.keyboards.clan import (
    back_menu,
    delete_confirm_menu,
    edit_menu,
    kick_confirm_menu,
    members_pick_menu,
    rank_set_menu,
    ranks_menu,
    requests_menu,
    transfer_confirm_menu,
)
from bot.services import clan as clan_service
from bot.services.settings import notify_player
from bot.states.clan import ClanStates
from bot.texts.clan import (
    CREATE_PROMPT,
    DELETE_CONFIRM,
    DONE_ALERT,
    EDIT_DESCRIPTION_PROMPT,
    EDIT_IMAGE_PROMPT,
    EDIT_MENU,
    EDITED,
    ERRORS,
    INVITE_PROMPT,
    INVITE_SENT,
    KICK_CONFIRM,
    KICK_EMPTY,
    KICK_PROMPT,
    NAME_INVALID,
    PUSH_ACCEPTED,
    PUSH_DELETED,
    PUSH_INVITE,
    PUSH_KICKED,
    RANK_EMOJI,
    RANK_NAME,
    RANK_PICK,
    RANKS_HEADER,
    REQUESTS_EMPTY,
    REQUESTS_HEADER,
    TRANSFER_CONFIRM,
    TRANSFER_PROMPT,
)
from bot.utils.formatting import esc

router = Router(name="clan_manage")


async def _manager(callback: CallbackQuery, session: AsyncSession, ranks=MANAGER_RANKS):
    try:
        return await clan_service.require_member(session, callback.from_user.id, ranks)
    except clan_service.ClanError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return None


async def _label(session: AsyncSession, user_id: int) -> str:
    return (await clan_repo.member_labels(session, [user_id])).get(user_id, ("—", None))[0]


# --- заявки ---

async def _show_requests(callback: CallbackQuery, session: AsyncSession, clan_id: int) -> None:
    requests = await clan_repo.list_requests(session, clan_id, False)
    labels = await clan_repo.member_labels(session, [r.user_id for r in requests])
    items = [(r.user_id, labels[r.user_id][0]) for r in requests]
    await send_screen(callback.bot, callback.message.chat.id, callback.message, REQUESTS_HEADER + ("" if items else REQUESTS_EMPTY), requests_menu(items))


@router.callback_query(F.data == CB_CLAN_REQUESTS)
async def cb_requests(callback: CallbackQuery, session: AsyncSession) -> None:
    member = await _manager(callback, session)
    if member is None:
        return
    await callback.answer()
    await _show_requests(callback, session, member.clan_id)


@router.callback_query(F.data.startswith(CB_CLAN_ACCEPT_PREFIX))
async def cb_accept(callback: CallbackQuery, session: AsyncSession) -> None:
    raw = callback.data.removeprefix(CB_CLAN_ACCEPT_PREFIX)
    if not raw.isdigit():
        await callback.answer()
        return
    try:
        clan_id = await clan_service.accept(session, callback.from_user.id, int(raw))
    except clan_service.ClanError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    await callback.answer(DONE_ALERT)
    clan = await clan_repo.get(session, clan_id)
    await notify_player(callback.bot, session, int(raw), NOTIFY_CLAN, PUSH_ACCEPTED.format(clan=esc(clan.name)))
    await _show_requests(callback, session, clan_id)


@router.callback_query(F.data.startswith(CB_CLAN_REJECT_PREFIX))
async def cb_reject(callback: CallbackQuery, session: AsyncSession) -> None:
    raw = callback.data.removeprefix(CB_CLAN_REJECT_PREFIX)
    member = await _manager(callback, session)
    if member is None or not raw.isdigit():
        return
    await clan_service.reject(session, callback.from_user.id, int(raw))
    await callback.answer()
    await _show_requests(callback, session, member.clan_id)


# --- приглашение ---

@router.callback_query(F.data == CB_CLAN_INVITE)
async def cb_invite(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if await _manager(callback, session) is None:
        return
    await state.set_state(ClanStates.waiting_invite)
    await callback.answer()
    await send_screen(callback.bot, callback.message.chat.id, callback.message, INVITE_PROMPT, back_menu())


@router.message(ClanStates.waiting_invite)
async def on_invite(message: Message, state: FSMContext, session: AsyncSession) -> None:
    username = (message.text or "").strip()
    try:
        target_id, clan_id = await clan_service.invite(session, message.from_user.id, username)
    except clan_service.ClanError as exc:
        await message.answer(error_text(exc), reply_markup=back_menu())
        return
    await state.clear()
    clan = await clan_repo.get(session, clan_id)
    await notify_player(message.bot, session, target_id, NOTIFY_CLAN, PUSH_INVITE.format(clan=esc(clan.name)))
    await message.answer(INVITE_SENT.format(name=esc(username)), reply_markup=back_menu())


# --- ранги, передача, роспуск ---

async def _show_ranks(callback: CallbackQuery, session: AsyncSession, clan_id: int) -> None:
    members = [m for m in await clan_repo.list_members(session, clan_id) if m.rank != RANK_OWNER]
    labels = await clan_repo.member_labels(session, [m.user_id for m in members])
    items = [(m.user_id, f"{RANK_EMOJI[m.rank]} {labels[m.user_id][0]}") for m in members]
    await send_screen(callback.bot, callback.message.chat.id, callback.message, RANKS_HEADER, ranks_menu(items))


@router.callback_query(F.data == CB_CLAN_RANKS)
async def cb_ranks(callback: CallbackQuery, session: AsyncSession) -> None:
    member = await _manager(callback, session, (RANK_OWNER,))
    if member is None:
        return
    await callback.answer()
    await _show_ranks(callback, session, member.clan_id)


@router.callback_query(F.data.startswith(CB_CLAN_RANK_PREFIX))
async def cb_rank(callback: CallbackQuery, session: AsyncSession) -> None:
    member = await _manager(callback, session, (RANK_OWNER,))
    if member is None:
        return
    uid_raw, _, rank = callback.data.removeprefix(CB_CLAN_RANK_PREFIX).partition(":")
    if not uid_raw.isdigit():
        await callback.answer()
        return
    target_id = int(uid_raw)
    if not rank:
        target = await clan_repo.get_member(session, target_id)
        if target is None or target.clan_id != member.clan_id:
            await callback.answer(ERRORS["not_member"], show_alert=True)
            return
        await callback.answer()
        text = RANK_PICK.format(name=esc(await _label(session, target_id)), rank=RANK_NAME[target.rank])
        await send_screen(callback.bot, callback.message.chat.id, callback.message, text, rank_set_menu(target_id))
        return
    try:
        await clan_service.set_rank(session, callback.from_user.id, target_id, rank)
    except clan_service.ClanError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    await callback.answer(DONE_ALERT)
    await _show_ranks(callback, session, member.clan_id)


@router.callback_query(F.data == CB_CLAN_TRANSFER)
async def cb_transfer(callback: CallbackQuery, session: AsyncSession) -> None:
    member = await _manager(callback, session, (RANK_OWNER,))
    if member is None:
        return
    members = [m for m in await clan_repo.list_members(session, member.clan_id) if m.rank != RANK_OWNER]
    labels = await clan_repo.member_labels(session, [m.user_id for m in members])
    await callback.answer()
    await send_screen(callback.bot, callback.message.chat.id, callback.message, TRANSFER_PROMPT,
                      members_pick_menu([(m.user_id, labels[m.user_id][0]) for m in members], CB_CLAN_TRANSFER_PREFIX, CB_CLAN_RANKS))


@router.callback_query(F.data.startswith(CB_CLAN_TRANSFER_PREFIX))
async def cb_transfer_pick(callback: CallbackQuery, session: AsyncSession) -> None:
    member = await _manager(callback, session, (RANK_OWNER,))
    if member is None:
        return
    uid_raw, _, ok = callback.data.removeprefix(CB_CLAN_TRANSFER_PREFIX).partition(":")
    if not uid_raw.isdigit():
        await callback.answer()
        return
    if not ok:
        clan = await clan_repo.get(session, member.clan_id)
        await callback.answer()
        text = TRANSFER_CONFIRM.format(clan=esc(clan.name), name=esc(await _label(session, int(uid_raw))))
        await send_screen(callback.bot, callback.message.chat.id, callback.message, text, transfer_confirm_menu(int(uid_raw)))
        return
    try:
        await clan_service.transfer(session, callback.from_user.id, int(uid_raw))
    except clan_service.ClanError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    await callback.answer(DONE_ALERT)
    await render_clan(callback.bot, callback.message.chat.id, session, callback.from_user.id, callback.message)


@router.callback_query(F.data == CB_CLAN_DELETE)
async def cb_delete(callback: CallbackQuery, session: AsyncSession) -> None:
    member = await _manager(callback, session, (RANK_OWNER,))
    if member is None:
        return
    clan = await clan_repo.get(session, member.clan_id)
    await callback.answer()
    await send_screen(callback.bot, callback.message.chat.id, callback.message, DELETE_CONFIRM.format(clan=esc(clan.name)), delete_confirm_menu())


@router.callback_query(F.data == CB_CLAN_DELETE_CONFIRM)
async def cb_delete_confirm(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        name, others = await clan_service.delete(session, callback.from_user.id)
    except clan_service.ClanError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    await callback.answer(DONE_ALERT, show_alert=True)
    for uid in others:
        await notify_player(callback.bot, session, uid, NOTIFY_CLAN, PUSH_DELETED.format(clan=esc(name)))
    await render_clan(callback.bot, callback.message.chat.id, session, callback.from_user.id, callback.message)


# --- исключение ---

@router.callback_query(F.data == CB_CLAN_KICK)
async def cb_kick(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        items = await clan_service.kickable(session, callback.from_user.id)
    except clan_service.ClanError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    await callback.answer()
    await send_screen(callback.bot, callback.message.chat.id, callback.message, KICK_PROMPT if items else KICK_EMPTY,
                      members_pick_menu(items, CB_CLAN_KICK_PREFIX))


@router.callback_query(F.data.startswith(CB_CLAN_KICK_PREFIX))
async def cb_kick_pick(callback: CallbackQuery, session: AsyncSession) -> None:
    uid_raw, _, ok = callback.data.removeprefix(CB_CLAN_KICK_PREFIX).partition(":")
    if not uid_raw.isdigit():
        await callback.answer()
        return
    if not ok:
        await callback.answer()
        await send_screen(callback.bot, callback.message.chat.id, callback.message,
                          KICK_CONFIRM.format(name=esc(await _label(session, int(uid_raw)))), kick_confirm_menu(int(uid_raw)))
        return
    try:
        clan_name = await clan_service.kick(session, callback.from_user.id, int(uid_raw))
    except clan_service.ClanError as exc:
        await callback.answer(error_text(exc), show_alert=True)
        return
    await callback.answer(DONE_ALERT)
    await notify_player(callback.bot, session, int(uid_raw), NOTIFY_CLAN, PUSH_KICKED.format(clan=esc(clan_name)))
    await render_clan(callback.bot, callback.message.chat.id, session, callback.from_user.id, callback.message)


# --- редактирование ---

@router.callback_query(F.data == CB_CLAN_EDIT)
async def cb_edit(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    member = await _manager(callback, session)
    if member is None:
        return
    await callback.answer()
    await send_screen(callback.bot, callback.message.chat.id, callback.message, EDIT_MENU, edit_menu(await clan_service.can_set_image(session, member.clan_id)))


@router.callback_query(F.data == CB_CLAN_EDIT_NAME)
async def cb_edit_name(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if await _manager(callback, session) is None:
        return
    await state.set_state(ClanStates.waiting_edit_name)
    await callback.answer()
    await send_screen(callback.bot, callback.message.chat.id, callback.message, CREATE_PROMPT.format(min=CLAN_NAME_MIN, max=CLAN_NAME_MAX), back_menu(CB_CLAN_EDIT))


@router.message(ClanStates.waiting_edit_name)
async def on_edit_name(message: Message, state: FSMContext, session: AsyncSession) -> None:
    name = (message.text or "").strip()
    if not valid_name(name):
        await message.answer(NAME_INVALID.format(min=CLAN_NAME_MIN, max=CLAN_NAME_MAX), reply_markup=back_menu(CB_CLAN_EDIT))
        return
    try:
        await clan_service.edit(session, message.from_user.id, name=name)
    except clan_service.ClanError as exc:
        await message.answer(error_text(exc), reply_markup=back_menu(CB_CLAN_EDIT))
        return
    await state.clear()
    await message.answer(EDITED, reply_markup=back_menu(CB_CLAN_EDIT))


@router.callback_query(F.data == CB_CLAN_EDIT_DESCRIPTION)
async def cb_edit_description(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if await _manager(callback, session) is None:
        return
    await state.set_state(ClanStates.waiting_edit_description)
    await callback.answer()
    await send_screen(callback.bot, callback.message.chat.id, callback.message, EDIT_DESCRIPTION_PROMPT.format(max=CLAN_DESCRIPTION_MAX), back_menu(CB_CLAN_EDIT))


@router.message(ClanStates.waiting_edit_description)
async def on_edit_description(message: Message, state: FSMContext, session: AsyncSession) -> None:
    text = (message.text or "").strip()
    if not text or len(text) > CLAN_DESCRIPTION_MAX:
        await message.answer(EDIT_DESCRIPTION_PROMPT.format(max=CLAN_DESCRIPTION_MAX), reply_markup=back_menu(CB_CLAN_EDIT))
        return
    try:
        await clan_service.edit(session, message.from_user.id, description=text)
    except clan_service.ClanError as exc:
        await message.answer(error_text(exc), reply_markup=back_menu(CB_CLAN_EDIT))
        return
    await state.clear()
    await message.answer(EDITED, reply_markup=back_menu(CB_CLAN_EDIT))


@router.callback_query(F.data == CB_CLAN_EDIT_IMAGE)
async def cb_edit_image(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    member = await _manager(callback, session)
    if member is None:
        return
    if not await clan_service.can_set_image(session, member.clan_id):
        await callback.answer(ERRORS["not_top"].format(value=10), show_alert=True)
        return
    await state.set_state(ClanStates.waiting_image)
    await callback.answer()
    await send_screen(callback.bot, callback.message.chat.id, callback.message, EDIT_IMAGE_PROMPT, back_menu(CB_CLAN_EDIT))


@router.message(ClanStates.waiting_image, F.photo)
async def on_edit_image(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        await clan_service.set_image(session, message.from_user.id, message.photo[-1].file_id)
    except clan_service.ClanError as exc:
        await state.clear()
        await message.answer(error_text(exc), reply_markup=back_menu(CB_CLAN_EDIT))
        return
    await state.clear()
    await message.answer(EDITED)
    await render_clan(message.bot, message.chat.id, session, message.from_user.id)


@router.message(ClanStates.waiting_image)
async def on_edit_image_invalid(message: Message) -> None:
    await message.answer(EDIT_IMAGE_PROMPT, reply_markup=back_menu(CB_CLAN_EDIT))
