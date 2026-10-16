"""Админка — Кланы (хендлеры)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.admin import CB_ADMIN_SECTION_PREFIX, SECTION_CLANS
from bot.constant.admin import clans_admin as C
from bot.handlers.admin.common import guard, parse_id
from bot.keyboards.admin import clans_admin as K
from bot.services.admin import clans_admin as svc
from bot.services.admin import roles
from bot.states.admin_clans import AdminClansStates
from bot.texts.admin import clans_admin as T
from bot.utils.formatting import esc, format_countdown, format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="admin_clans")


async def _card_screen(session: AsyncSession, clan_id: int) -> tuple[str, InlineKeyboardMarkup] | None:
    card = await svc.card(session, clan_id)
    if card is None:
        return None
    clan = card.clan
    members = "\n".join(T.MEMBER_LINE.format(rank=rank, label=esc(label)) for _, rank, label in card.members)
    text = T.CLAN_CARD.format(
        name=esc(clan.name), id=clan.id, owner=esc(card.owner_label), members=len(card.members), lands=clan.lands,
        treasury=format_number(clan.treasury), donate_level=clan.donate_level, buyers=card.buyers,
        paid=format_number(card.paid), power=format_number(card.power),
        shield=format_countdown(card.shield) if card.shield else T.NONE_SHORT,
        cooldown=format_countdown(card.cooldown) if card.cooldown else T.NONE_SHORT, members_list=members,
    )
    return text, K.clan_card(clan_id)


async def _show_card(callback: CallbackQuery, session: AsyncSession, clan_id: int) -> None:
    screen = await _card_screen(session, clan_id)
    if screen is None:
        await callback.answer(T.ALERT_STALE, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(callback.message, screen[0], reply_markup=screen[1])


@router.callback_query(F.data == f"{CB_ADMIN_SECTION_PREFIX}{SECTION_CLANS}")
async def cb_section(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_CLANS):
        return
    await state.clear()
    await callback.answer()
    await safe_edit_text(callback.message, T.MENU, reply_markup=K.menu())


@router.callback_query(F.data == C.CB_C_FIND)
async def cb_find(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_CLANS):
        return
    await state.set_state(AdminClansStates.waiting_clan)
    await callback.answer()
    await safe_edit_text(callback.message, T.ASK_CLAN, reply_markup=K.back_to_section())


@router.message(StateFilter(AdminClansStates.waiting_clan), F.text)
async def msg_clan(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not await roles.can(session, message.from_user.id, SECTION_CLANS):
        return
    clans = await svc.find(session, message.text)
    if not clans:
        await message.answer(T.CLAN_NOT_FOUND, reply_markup=K.back_to_section())
        return
    await state.clear()
    if len(clans) == 1:
        screen = await _card_screen(session, clans[0].id)
        await message.answer(screen[0], reply_markup=screen[1])
        return
    await message.answer(T.PICK_CLAN, reply_markup=K.pick_clans([(c.id, c.name) for c in clans]))


@router.callback_query(F.data.startswith(C.CB_C_VIEW_PREFIX))
async def cb_view(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if not await guard(callback, session, SECTION_CLANS):
        return
    clan_id = parse_id(callback.data, C.CB_C_VIEW_PREFIX)
    if clan_id is None:
        return
    await state.clear()
    await _show_card(callback, session, clan_id)


# --- передача владения ---

@router.callback_query(F.data.startswith(C.CB_C_TRANSFER_PREFIX))
async def cb_transfer(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_CLANS):
        return
    clan_id = parse_id(callback.data, C.CB_C_TRANSFER_PREFIX)
    card = await svc.card(session, clan_id) if clan_id is not None else None
    if card is None:
        await callback.answer(T.ALERT_STALE, show_alert=True)
        return
    others = [(uid, f"{rank} {label}") for uid, rank, label in card.members if uid != card.clan.owner_id]
    if not others:
        await callback.answer(T.ALERT_NO_RANK_OTHERS, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(callback.message, T.PICK_OWNER.format(name=esc(card.clan.name)), reply_markup=K.pick_owner(clan_id, others))


def _two_ids(data: str, prefix: str) -> tuple[int, int] | None:
    parts = data.removeprefix(prefix).split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        return None
    return int(parts[0]), int(parts[1])


@router.callback_query(F.data.startswith(C.CB_C_TRANSFER_PICK_PREFIX))
async def cb_transfer_pick(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_CLANS):
        return
    ids = _two_ids(callback.data, C.CB_C_TRANSFER_PICK_PREFIX)
    card = await svc.card(session, ids[0]) if ids else None
    target = next((m for m in card.members if m[0] == ids[1]), None) if card else None
    if target is None:
        await callback.answer(T.ALERT_NOT_MEMBER, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(
        callback.message, T.CONFIRM_TRANSFER.format(name=esc(card.clan.name), target=esc(target[2])),
        reply_markup=K.confirm_transfer(ids[0], ids[1]),
    )


@router.callback_query(F.data.startswith(C.CB_C_TRANSFER_OK_PREFIX))
async def cb_transfer_ok(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_CLANS):
        return
    ids = _two_ids(callback.data, C.CB_C_TRANSFER_OK_PREFIX)
    if ids is None:
        return
    ok = await svc.transfer_owner(session, callback.from_user.id, ids[0], ids[1])
    await callback.answer(T.DONE_TRANSFER if ok else T.ALERT_NOT_MEMBER, show_alert=True)
    await _show_card(callback, session, ids[0])


# --- числовые поля ---

async def _ask_value(callback: CallbackQuery, session: AsyncSession, state: FSMContext, prefix: str, field: str) -> None:
    if not await guard(callback, session, SECTION_CLANS):
        return
    clan_id = parse_id(callback.data, prefix)
    clan = await svc.clan_repo.get(session, clan_id) if clan_id is not None else None
    if clan is None:
        await callback.answer(T.ALERT_STALE, show_alert=True)
        return
    if field == C.FIELD_LANDS:
        text = T.ASK_LANDS.format(name=esc(clan.name), current=clan.lands, min=svc.LANDS_MIN, max=svc.LANDS_MAX)
    elif field == C.FIELD_TREASURY:
        text = T.ASK_TREASURY.format(name=esc(clan.name), current=format_number(clan.treasury))
    else:
        text = T.ASK_DONATE.format(name=esc(clan.name), current=clan.donate_level, max=svc.DONATE_MAX)
    await state.set_state(AdminClansStates.waiting_value)
    await state.update_data({C.FSM_CLAN_ID: clan_id, C.FSM_FIELD: field})
    await callback.answer()
    await safe_edit_text(callback.message, text, reply_markup=K.to_clan(clan_id))


@router.callback_query(F.data.startswith(C.CB_C_LANDS_PREFIX))
async def cb_lands(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await _ask_value(callback, session, state, C.CB_C_LANDS_PREFIX, C.FIELD_LANDS)


@router.callback_query(F.data.startswith(C.CB_C_TREASURY_PREFIX))
async def cb_treasury(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await _ask_value(callback, session, state, C.CB_C_TREASURY_PREFIX, C.FIELD_TREASURY)


@router.callback_query(F.data.startswith(C.CB_C_DONATE_PREFIX))
async def cb_donate(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await _ask_value(callback, session, state, C.CB_C_DONATE_PREFIX, C.FIELD_DONATE)


@router.message(StateFilter(AdminClansStates.waiting_value), F.text)
async def msg_value(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not await roles.can(session, message.from_user.id, SECTION_CLANS):
        return
    data = await state.get_data()
    clan_id, field = data[C.FSM_CLAN_ID], data[C.FSM_FIELD]
    raw = message.text.strip().replace(" ", "")
    if not raw.lstrip("+-").isdigit():
        await message.answer(T.BAD_NUMBER, reply_markup=K.to_clan(clan_id))
        return
    value = int(raw)
    admin_id = message.from_user.id
    if field == C.FIELD_LANDS:
        if not await svc.set_lands(session, admin_id, clan_id, value):
            await message.answer(T.OUT_OF_RANGE.format(min=svc.LANDS_MIN, max=svc.LANDS_MAX), reply_markup=K.to_clan(clan_id))
            return
        note = T.DONE_LANDS.format(value=value)
    elif field == C.FIELD_TREASURY:
        new = await svc.change_treasury(session, admin_id, clan_id, value)
        if new is None:
            await message.answer(T.TREASURY_TOO_LOW, reply_markup=K.to_clan(clan_id))
            return
        note = T.DONE_TREASURY.format(delta=f"{value:+d}", value=format_number(new))
    else:
        if not await svc.set_donate_level(session, admin_id, clan_id, value):
            await message.answer(T.OUT_OF_RANGE.format(min=0, max=svc.DONATE_MAX), reply_markup=K.to_clan(clan_id))
            return
        note = T.DONE_DONATE.format(value=value)
    await state.clear()
    await message.answer(note, reply_markup=K.to_clan(clan_id))


# --- щит / КД ---

@router.callback_query(F.data.startswith(C.CB_C_SHIELD_PREFIX))
async def cb_shield(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_CLANS):
        return
    clan_id = parse_id(callback.data, C.CB_C_SHIELD_PREFIX)
    ok = await svc.remove_shield(session, callback.from_user.id, clan_id) if clan_id is not None else False
    await callback.answer(T.DONE_SHIELD if ok else T.ALERT_NO_SHIELD, show_alert=True)
    if clan_id is not None:
        await _show_card(callback, session, clan_id)


@router.callback_query(F.data.startswith(C.CB_C_COOLDOWN_PREFIX))
async def cb_cooldown(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_CLANS):
        return
    clan_id = parse_id(callback.data, C.CB_C_COOLDOWN_PREFIX)
    ok = await svc.remove_cooldown(session, callback.from_user.id, clan_id) if clan_id is not None else False
    await callback.answer(T.DONE_COOLDOWN if ok else T.ALERT_NO_COOLDOWN, show_alert=True)
    if clan_id is not None:
        await _show_card(callback, session, clan_id)


# --- удаление ---

@router.callback_query(F.data.startswith(C.CB_C_DELETE_PREFIX))
async def cb_delete(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_CLANS):
        return
    clan_id = parse_id(callback.data, C.CB_C_DELETE_PREFIX)
    card = await svc.card(session, clan_id) if clan_id is not None else None
    if card is None:
        await callback.answer(T.ALERT_STALE, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(
        callback.message, T.CONFIRM_DELETE.format(name=esc(card.clan.name), members=len(card.members)),
        reply_markup=K.confirm_delete(clan_id),
    )


@router.callback_query(F.data.startswith(C.CB_C_DELETE_OK_PREFIX))
async def cb_delete_ok(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await guard(callback, session, SECTION_CLANS):
        return
    clan_id = parse_id(callback.data, C.CB_C_DELETE_OK_PREFIX)
    result = await svc.delete_clan(session, callback.from_user.id, clan_id) if clan_id is not None else None
    if result is None:
        await callback.answer(T.ALERT_STALE, show_alert=True)
        return
    await callback.answer(T.DONE_DELETE.format(total=result[2]), show_alert=True)
    await safe_edit_text(callback.message, T.MENU, reply_markup=K.menu())
