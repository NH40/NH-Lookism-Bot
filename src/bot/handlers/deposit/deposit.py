"""Вклады (хендлеры). Вход — «🏦 Вклады» в магазине."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.deposit import DEPOSIT_MAX_ACTIVE, DEPOSIT_RATES
from bot.constant.deposit import (
    CB_DEPOSIT_CLAIM_PREFIX,
    CB_DEPOSIT_NEW,
    CB_DEPOSIT_OPEN,
    CB_DEPOSIT_RES_PREFIX,
    CB_DEPOSIT_TERM_PREFIX,
)
from bot.constant.resource import RESOURCES
from bot.keyboards.deposit import back_to_deposits, deposits_menu, resources_menu, terms_menu
from bot.services.deposit import (
    DepositBusyError,
    DepositNotFoundError,
    InvalidAmountError,
    InvalidTermError,
    NotEnoughError,
    TooManyDepositsError,
    cap_for,
    claim,
    list_deposits,
    open_deposit,
    rate_for,
)
from bot.services.gang import get_gang
from bot.services.resource import balance
from bot.states.deposit import DepositStates
from bot.texts.deposit import (
    AMOUNT_INVALID,
    AMOUNT_PROMPT,
    BUSY_ALERT,
    CLAIMED_ALERT,
    CLAIMED_EARLY_ALERT,
    DEPOSIT_NONE,
    DEPOSIT_ROW_READY,
    DEPOSIT_ROW_WAIT,
    DEPOSIT_SCREEN,
    NOT_ENOUGH_ALERT,
    NOT_FOUND_ALERT,
    OPENED,
    PICK_RESOURCE,
    PICK_TERM,
    TOO_MANY_ALERT,
)
from bot.texts.profile import NOT_ONBOARDED
from bot.texts.resource import amount_label, resource_label
from bot.utils.formatting import format_countdown
from bot.utils.safe_edit import safe_edit_text

router = Router(name="deposit")


async def render_deposits(session: AsyncSession, user_id: int):
    deposits = await list_deposits(session, user_id)
    rows = "".join(
        (DEPOSIT_ROW_READY if d.ready else DEPOSIT_ROW_WAIT).format(
            id=d.id, amount=amount_label(d.resource, d.amount), payout=amount_label(d.resource, d.payout),
            countdown=format_countdown(d.left_seconds),
        )
        for d in deposits
    ) or DEPOSIT_NONE
    text = DEPOSIT_SCREEN.format(max=DEPOSIT_MAX_ACTIVE, rows=rows)
    return text, deposits_menu(deposits, can_open=len(deposits) < DEPOSIT_MAX_ACTIVE)


async def _guard(callback: CallbackQuery, session: AsyncSession) -> bool:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return False
    return True


@router.callback_query(F.data == CB_DEPOSIT_OPEN)
async def cb_deposit_open(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    if not await _guard(callback, session):
        return
    await callback.answer()
    text, markup = await render_deposits(session, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data == CB_DEPOSIT_NEW)
async def cb_deposit_new(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _guard(callback, session):
        return
    await callback.answer()
    await safe_edit_text(callback.message, PICK_RESOURCE, reply_markup=resources_menu())


@router.callback_query(F.data.startswith(CB_DEPOSIT_RES_PREFIX))
async def cb_deposit_resource(callback: CallbackQuery, session: AsyncSession) -> None:
    resource = callback.data.removeprefix(CB_DEPOSIT_RES_PREFIX)
    if resource not in RESOURCES or not await _guard(callback, session):
        await callback.answer()
        return
    cap = await cap_for(session, callback.from_user.id, resource)
    await callback.answer()
    await safe_edit_text(
        callback.message,
        PICK_TERM.format(resource=resource_label(resource), cap=amount_label(resource, cap)),
        reply_markup=terms_menu(resource, {h: rate_for(resource, h) for h in DEPOSIT_RATES}),
    )


@router.callback_query(F.data.startswith(CB_DEPOSIT_TERM_PREFIX))
async def cb_deposit_term(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    resource, _, raw = callback.data.removeprefix(CB_DEPOSIT_TERM_PREFIX).rpartition(":")
    if resource not in RESOURCES or not raw.isdigit() or int(raw) not in DEPOSIT_RATES or not await _guard(callback, session):
        await callback.answer()
        return
    hours, user_id = int(raw), callback.from_user.id
    cap = await cap_for(session, user_id, resource)
    await state.set_state(DepositStates.waiting_amount)
    await state.update_data(resource=resource, hours=hours)
    await callback.answer()
    await safe_edit_text(
        callback.message,
        AMOUNT_PROMPT.format(
            resource=resource_label(resource), hours=hours, percent=f"{rate_for(resource, hours) * 100:g}",
            have=amount_label(resource, await balance(session, user_id, resource)), cap=amount_label(resource, cap),
        ),
        reply_markup=back_to_deposits(),
    )


@router.message(DepositStates.waiting_amount)
async def on_deposit_amount(message: Message, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    data = await state.get_data()
    resource, hours = data.get("resource", ""), data.get("hours", 0)
    raw = (message.text or "").replace(" ", "").replace("_", "")
    user_id = message.from_user.id
    try:
        if not raw.isdigit():
            raise InvalidAmountError(await cap_for(session, user_id, resource))
        deposit = await open_deposit(session, redis, user_id, resource, hours, int(raw))
    except InvalidAmountError as exc:
        await message.answer(AMOUNT_INVALID.format(cap=amount_label(resource, exc.cap)), reply_markup=back_to_deposits())
        return
    except NotEnoughError:
        await message.answer(NOT_ENOUGH_ALERT, reply_markup=back_to_deposits())
        return
    except DepositBusyError:
        await message.answer(BUSY_ALERT)
        return
    except (TooManyDepositsError, InvalidTermError):
        await state.clear()
        await message.answer(TOO_MANY_ALERT.format(max=DEPOSIT_MAX_ACTIVE), reply_markup=back_to_deposits())
        return
    await state.clear()
    await message.answer(
        OPENED.format(
            id=deposit.id, amount=amount_label(resource, deposit.amount), hours=hours,
            payout=amount_label(resource, deposit.payout),
        )
    )
    text, markup = await render_deposits(session, user_id)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_DEPOSIT_CLAIM_PREFIX))
async def cb_deposit_claim(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    raw = callback.data.removeprefix(CB_DEPOSIT_CLAIM_PREFIX)
    if not raw.isdigit() or not await _guard(callback, session):
        await callback.answer()
        return
    deposits = {d.id: d for d in await list_deposits(session, callback.from_user.id)}
    resource = deposits[int(raw)].resource if int(raw) in deposits else ""
    # Popup-тексты — без HTML.
    try:
        amount, matured = await claim(session, redis, callback.from_user.id, int(raw))
    except DepositBusyError:
        await callback.answer(BUSY_ALERT)
        return
    except DepositNotFoundError:
        await callback.answer(NOT_FOUND_ALERT, show_alert=True)
        return
    template = CLAIMED_ALERT if matured else CLAIMED_EARLY_ALERT
    await callback.answer(template.format(amount=amount_label(resource, amount)), show_alert=True)
    text, markup = await render_deposits(session, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)
