"""Ячейки хранения (хендлеры). Вход — «🗄 Ячейки» в магазине."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.storage import STORAGE_FEE_PER_HOUR
from bot.constant.resource import RESOURCES
from bot.constant.storage import (
    CB_STORAGE_CELL_PREFIX,
    CB_STORAGE_OPEN,
    CB_STORAGE_PUT_RES_PREFIX,
    CB_STORAGE_PUT_SQUAD_PREFIX,
    CB_STORAGE_PUT_STATISTS_PREFIX,
    CB_STORAGE_TAKE_ALL_PREFIX,
    CB_STORAGE_TAKE_PART_PREFIX,
    CB_STORAGE_TOPUP_PREFIX,
    CB_STORAGE_UNLOCK_PREFIX,
    STORAGE_ITEM_RESOURCE,
    STORAGE_ITEM_STATIST,
)
from bot.keyboards.storage import back_to_cell, empty_cell_menu, filled_cell_menu, squads_menu, storage_menu
from bot.services.extra import list_squads
from bot.services.gang import get_gang
from bot.services.resource import StatistKey, balance
from bot.services.storage import (
    CellEmptyError,
    CellLockedError,
    CellOccupiedError,
    InvalidAmountError,
    NotEnoughCoinsError,
    NotEnoughError,
    StorageBusyError,
    cells,
    open_cell,
    retrieve,
    store_resource,
    store_statists,
)
from bot.states.storage import StorageStates
from bot.texts.gang import squad_title
from bot.texts.profile import NOT_ONBOARDED
from bot.texts.resource import resource_label
from bot.texts.storage import (
    AMOUNT_INVALID,
    AMOUNT_PUT,
    AMOUNT_TAKE,
    BUSY_ALERT,
    CELL_DEBT,
    CELL_LINE_EMPTY,
    CELL_LINE_ITEM,
    CELL_LINE_LOCKED,
    CELL_SCREEN_EMPTY,
    CELL_SCREEN_ITEM,
    EMPTY_ALERT,
    LOCKED_ALERT,
    NOT_ENOUGH_ALERT,
    NOT_ENOUGH_COINS_ALERT,
    OCCUPIED_ALERT,
    OPENED_ALERT,
    PICK_SQUAD,
    PICK_SQUAD_NONE,
    STORAGE_SCREEN,
    STORED,
    TAKEN,
    TAKEN_PAID,
)
from bot.utils.formatting import format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="storage")

_ACTION_PUT = "put"
_ACTION_TAKE = "take"


def item_label(kind: str, code: str) -> str:
    if kind == STORAGE_ITEM_RESOURCE:
        return resource_label(code)
    key = StatistKey.decode(code)
    return "👥 " + squad_title(key.rank, key.stars, key.training_level, key.school, key.school_level)


async def render_storage(session: AsyncSession, user_id: int):
    views = await cells(session, user_id)
    lines = ""
    for v in views:
        if not v.opened:
            lines += CELL_LINE_LOCKED.format(n=v.slot, cost=format_number(v.open_cost))
        elif v.empty:
            lines += CELL_LINE_EMPTY.format(n=v.slot)
        else:
            lines += CELL_LINE_ITEM.format(
                n=v.slot, item=item_label(v.kind, v.code), amount=format_number(v.amount),
                debt=CELL_DEBT.format(debt=format_number(v.debt)) if v.debt else "",
            )
    text = STORAGE_SCREEN.format(fee=format_number(STORAGE_FEE_PER_HOUR), cells=lines)
    return text, storage_menu(views, lambda v: item_label(v.kind, v.code))


async def render_cell(session: AsyncSession, user_id: int, slot: int):
    view = next((v for v in await cells(session, user_id) if v.slot == slot), None)
    if view is None or not view.opened:
        return None
    if view.empty:
        return CELL_SCREEN_EMPTY.format(n=slot), empty_cell_menu(slot)
    text = CELL_SCREEN_ITEM.format(
        n=slot, item=item_label(view.kind, view.code), amount=format_number(view.amount), debt=format_number(view.debt)
    )
    return text, filled_cell_menu(slot)


async def _guard(callback: CallbackQuery, session: AsyncSession) -> bool:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return False
    return True


def _slot(raw: str) -> int | None:
    return int(raw) if raw.isdigit() else None


async def _show_cell(callback: CallbackQuery, session: AsyncSession, slot: int) -> None:
    rendered = await render_cell(session, callback.from_user.id, slot)
    if rendered is None:
        await callback.answer(LOCKED_ALERT, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(callback.message, rendered[0], reply_markup=rendered[1])


@router.callback_query(F.data == CB_STORAGE_OPEN)
async def cb_storage_open(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    if not await _guard(callback, session):
        return
    await callback.answer()
    text, markup = await render_storage(session, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_STORAGE_CELL_PREFIX))
async def cb_storage_cell(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    # Точка возврата «Назад» из ввода количества.
    await state.clear()
    slot = _slot(callback.data.removeprefix(CB_STORAGE_CELL_PREFIX))
    if slot is None or not await _guard(callback, session):
        await callback.answer()
        return
    await _show_cell(callback, session, slot)


@router.callback_query(F.data.startswith(CB_STORAGE_UNLOCK_PREFIX))
async def cb_storage_unlock(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    slot = _slot(callback.data.removeprefix(CB_STORAGE_UNLOCK_PREFIX))
    if slot is None or not await _guard(callback, session):
        await callback.answer()
        return
    # Popup-тексты — без HTML.
    try:
        cost = await open_cell(session, redis, callback.from_user.id, slot)
    except StorageBusyError:
        await callback.answer(BUSY_ALERT)
        return
    except CellLockedError:
        await callback.answer(LOCKED_ALERT, show_alert=True)
        return
    except NotEnoughCoinsError as exc:
        await callback.answer(NOT_ENOUGH_COINS_ALERT.format(cost=format_number(exc.cost)), show_alert=True)
        return
    await callback.answer(OPENED_ALERT.format(n=slot, cost=format_number(cost)), show_alert=True)
    text, markup = await render_storage(session, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)


async def _ask_amount(callback: CallbackQuery, state: FSMContext, slot: int, action: str, kind: str, code: str, have: int) -> None:
    await state.set_state(StorageStates.waiting_amount)
    await state.update_data(slot=slot, action=action, kind=kind, code=code)
    await callback.answer()
    template = AMOUNT_PUT if action == _ACTION_PUT else AMOUNT_TAKE
    await safe_edit_text(
        callback.message, template.format(item=item_label(kind, code), have=format_number(have)), reply_markup=back_to_cell(slot)
    )


@router.callback_query(F.data.startswith(CB_STORAGE_PUT_RES_PREFIX))
async def cb_storage_put_resource(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    raw_slot, _, code = callback.data.removeprefix(CB_STORAGE_PUT_RES_PREFIX).partition(":")
    slot = _slot(raw_slot)
    if slot is None or code not in RESOURCES or not await _guard(callback, session):
        await callback.answer()
        return
    have = await balance(session, callback.from_user.id, code)
    await _ask_amount(callback, state, slot, _ACTION_PUT, STORAGE_ITEM_RESOURCE, code, have)


@router.callback_query(F.data.startswith(CB_STORAGE_PUT_STATISTS_PREFIX))
async def cb_storage_put_statists(callback: CallbackQuery, session: AsyncSession) -> None:
    slot = _slot(callback.data.removeprefix(CB_STORAGE_PUT_STATISTS_PREFIX))
    if slot is None or not await _guard(callback, session):
        await callback.answer()
        return
    squads = [
        (
            StatistKey(sq.rank, sq.stars, sq.training_level, sq.school, sq.school_level).encode(),
            squad_title(sq.rank, sq.stars, sq.training_level, sq.school, sq.school_level),
            sq.attack + sq.defense,
        )
        for sq in await list_squads(session, callback.from_user.id)
        if sq.attack + sq.defense > 0
    ]
    if not squads:
        await callback.answer(PICK_SQUAD_NONE, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(callback.message, PICK_SQUAD.format(n=slot), reply_markup=squads_menu(slot, squads))


@router.callback_query(F.data.startswith(CB_STORAGE_PUT_SQUAD_PREFIX))
async def cb_storage_put_squad(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    raw_slot, _, code = callback.data.removeprefix(CB_STORAGE_PUT_SQUAD_PREFIX).partition(":")
    slot = _slot(raw_slot)
    try:
        key = StatistKey.decode(code)
    except ValueError:
        key = None
    if slot is None or key is None or not await _guard(callback, session):
        await callback.answer()
        return
    squad = next(
        (sq for sq in await list_squads(session, callback.from_user.id)
         if (sq.rank, sq.stars, sq.training_level, sq.school, sq.school_level) == (key.rank, key.stars, key.training_level, key.school, key.school_level)),
        None,
    )
    await _ask_amount(callback, state, slot, _ACTION_PUT, STORAGE_ITEM_STATIST, code, (squad.attack + squad.defense) if squad else 0)


@router.callback_query(F.data.startswith(CB_STORAGE_TOPUP_PREFIX))
async def cb_storage_topup(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    slot = _slot(callback.data.removeprefix(CB_STORAGE_TOPUP_PREFIX))
    view = next((v for v in await cells(session, callback.from_user.id) if v.slot == slot), None) if slot else None
    if view is None or view.empty:
        await callback.answer(EMPTY_ALERT, show_alert=True)
        return
    if view.kind == STORAGE_ITEM_RESOURCE:
        have = await balance(session, callback.from_user.id, view.code)
    else:
        key = StatistKey.decode(view.code)
        squad = next(
            (sq for sq in await list_squads(session, callback.from_user.id)
             if (sq.rank, sq.stars, sq.training_level, sq.school, sq.school_level) == (key.rank, key.stars, key.training_level, key.school, key.school_level)),
            None,
        )
        have = (squad.attack + squad.defense) if squad else 0
    await _ask_amount(callback, state, slot, _ACTION_PUT, view.kind, view.code, have)


@router.callback_query(F.data.startswith(CB_STORAGE_TAKE_PART_PREFIX))
async def cb_storage_take_part(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    slot = _slot(callback.data.removeprefix(CB_STORAGE_TAKE_PART_PREFIX))
    view = next((v for v in await cells(session, callback.from_user.id) if v.slot == slot), None) if slot else None
    if view is None or view.empty:
        await callback.answer(EMPTY_ALERT, show_alert=True)
        return
    await _ask_amount(callback, state, slot, _ACTION_TAKE, view.kind, view.code, view.amount)


async def _take(session: AsyncSession, redis: Redis, user_id: int, slot: int, amount: int | None) -> str:
    view = next((v for v in await cells(session, user_id) if v.slot == slot), None)
    label = item_label(view.kind, view.code) if view and not view.empty else ""
    taken, paid = await retrieve(session, redis, user_id, slot, amount)
    return TAKEN.format(item=label, amount=format_number(taken), paid=TAKEN_PAID.format(debt=format_number(paid)) if paid else "")


@router.callback_query(F.data.startswith(CB_STORAGE_TAKE_ALL_PREFIX))
async def cb_storage_take_all(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    slot = _slot(callback.data.removeprefix(CB_STORAGE_TAKE_ALL_PREFIX))
    if slot is None or not await _guard(callback, session):
        await callback.answer()
        return
    try:
        done = await _take(session, redis, callback.from_user.id, slot, None)
    except StorageBusyError:
        await callback.answer(BUSY_ALERT)
        return
    except (CellLockedError, CellEmptyError):
        await callback.answer(EMPTY_ALERT, show_alert=True)
        return
    except NotEnoughCoinsError as exc:
        await callback.answer(NOT_ENOUGH_COINS_ALERT.format(cost=format_number(exc.cost)), show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(done)
    await _show_cell(callback, session, slot)


@router.message(StorageStates.waiting_amount)
async def on_storage_amount(message: Message, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    data = await state.get_data()
    slot, action, kind, code = data.get("slot"), data.get("action"), data.get("kind"), data.get("code")
    raw = (message.text or "").replace(" ", "").replace("_", "")
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer(AMOUNT_INVALID, reply_markup=back_to_cell(slot))
        return
    amount, user_id = int(raw), message.from_user.id
    try:
        if action == _ACTION_TAKE:
            text = await _take(session, redis, user_id, slot, amount)
        else:
            if kind == STORAGE_ITEM_RESOURCE:
                total = await store_resource(session, redis, user_id, slot, code, amount)
            else:
                total = await store_statists(session, redis, user_id, slot, StatistKey.decode(code), amount)
            text = STORED.format(n=slot, item=item_label(kind, code), amount=format_number(total))
    except StorageBusyError:
        await message.answer(BUSY_ALERT)
        return
    except (NotEnoughError, InvalidAmountError):
        await message.answer(NOT_ENOUGH_ALERT, reply_markup=back_to_cell(slot))
        return
    except CellOccupiedError:
        await state.clear()
        await message.answer(OCCUPIED_ALERT, reply_markup=back_to_cell(slot))
        return
    except (CellLockedError, CellEmptyError):
        await state.clear()
        await message.answer(EMPTY_ALERT, reply_markup=back_to_cell(slot))
        return
    except NotEnoughCoinsError as exc:
        await state.clear()
        await message.answer(NOT_ENOUGH_COINS_ALERT.format(cost=format_number(exc.cost)), reply_markup=back_to_cell(slot))
        return
    await state.clear()
    rendered = await render_cell(session, user_id, slot)
    await message.answer(text)
    if rendered:
        await message.answer(rendered[0], reply_markup=rendered[1])
