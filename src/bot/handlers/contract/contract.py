"""Контракты статистов (хендлеры): ранг до потолка влияния → количество → цена → найм.

Вход — «📜 Контракты статистов» в магазине.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.contract import CONTRACT_MAX_QUANTITY, CONTRACT_RANKS_PER_PAGE
from bot.constant.contract import CB_CONTRACT_BUY_PREFIX, CB_CONTRACT_OPEN, CB_CONTRACT_PAGE_PREFIX, CB_CONTRACT_RANK_PREFIX
from bot.db.repositories import business as business_repo
from bot.keyboards.contract import back_to_contracts, confirm_menu, ranks_menu
from bot.services.contract import (
    InvalidQuantityError,
    NotEnoughCoinsError,
    RankNotAvailableError,
    ShopBusyError,
    active,
    buy,
    quote,
    terms,
)
from bot.services.gang import get_gang
from bot.states.contract import ContractStates
from bot.texts.contract import (
    BOUGHT_ALERT,
    BUSY_ALERT,
    CONTRACT_ACTIVE_HEAD,
    CONTRACT_ACTIVE_LINE,
    CONTRACT_DISCOUNT_LINE,
    CONTRACT_SCREEN,
    NOT_ENOUGH_ALERT,
    QUANTITY_INVALID,
    QUANTITY_PROMPT,
    QUOTE_SCREEN,
    RANK_LOCKED_ALERT,
)
from bot.texts.profile import NOT_ONBOARDED
from bot.utils.formatting import format_countdown, format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="contract")


def _hours(value: float) -> str:
    return f"{value:g}"


async def _coins(session: AsyncSession, user_id: int) -> int:
    wallet = await business_repo.get_wallet(session, user_id)
    return wallet.nh_coins if wallet else 0


async def render_contracts(session: AsyncSession, user_id: int, page: int = 0):
    current = await terms(session, user_id)
    ranks = current.ranks
    pages = max(1, -(-len(ranks) // CONTRACT_RANKS_PER_PAGE))
    page = min(max(page, 0), pages - 1)
    chunk = ranks[page * CONTRACT_RANKS_PER_PAGE:(page + 1) * CONTRACT_RANKS_PER_PAGE]
    running = await active(session, user_id)
    lines = (
        CONTRACT_ACTIVE_HEAD
        + "".join(
            CONTRACT_ACTIVE_LINE.format(quantity=format_number(c.quantity), rank=c.rank, countdown=format_countdown(c.expires_in_seconds))
            for c in running
        )
        if running
        else ""
    )
    text = CONTRACT_SCREEN.format(hours=_hours(current.hours), ceiling=current.ceiling, active=lines)
    if current.discount:
        text += CONTRACT_DISCOUNT_LINE.format(percent=round(current.discount * 100))
    return text, ranks_menu([(r, current.unit_price(r)) for r in chunk], page, pages)


async def _guard(callback: CallbackQuery, session: AsyncSession) -> bool:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return False
    return True


@router.callback_query(F.data == CB_CONTRACT_OPEN)
async def cb_contract_open(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    # Точка возврата «Назад» из ввода количества — не оставляем висящее ожидание ввода.
    await state.clear()
    if not await _guard(callback, session):
        return
    await callback.answer()
    text, markup = await render_contracts(session, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_CONTRACT_PAGE_PREFIX))
async def cb_contract_page(callback: CallbackQuery, session: AsyncSession) -> None:
    raw = callback.data.removeprefix(CB_CONTRACT_PAGE_PREFIX)
    await callback.answer()
    text, markup = await render_contracts(session, callback.from_user.id, int(raw) if raw.isdigit() else 0)
    await safe_edit_text(callback.message, text, reply_markup=markup)


@router.callback_query(F.data.startswith(CB_CONTRACT_RANK_PREFIX))
async def cb_contract_rank(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await _guard(callback, session):
        return
    rank = callback.data.removeprefix(CB_CONTRACT_RANK_PREFIX)
    try:
        one = await quote(session, callback.from_user.id, rank, 1)
    except RankNotAvailableError:
        await callback.answer(RANK_LOCKED_ALERT, show_alert=True)
        return
    coins = await _coins(session, callback.from_user.id)
    await state.set_state(ContractStates.waiting_quantity)
    await state.update_data(rank=rank)
    await callback.answer()
    await safe_edit_text(
        callback.message,
        QUANTITY_PROMPT.format(
            rank=rank, power=format_number(one.power), price=format_number(one.unit_price), hours=_hours(one.hours),
            coins=format_number(coins), affordable=format_number(coins // one.unit_price),
        ),
        reply_markup=back_to_contracts(),
    )


def _parse_quantity(text: str) -> int | None:
    raw = text.replace(" ", "").replace("_", "").replace(",", "")
    return int(raw) if raw.isdigit() else None


@router.message(ContractStates.waiting_quantity)
async def on_contract_quantity(message: Message, state: FSMContext, session: AsyncSession) -> None:
    rank = (await state.get_data()).get("rank", "")
    quantity = _parse_quantity(message.text or "")
    try:
        if quantity is None:
            raise InvalidQuantityError
        offer = await quote(session, message.from_user.id, rank, quantity)
    except InvalidQuantityError:
        await message.answer(QUANTITY_INVALID.format(max=format_number(CONTRACT_MAX_QUANTITY)), reply_markup=back_to_contracts())
        return
    except RankNotAvailableError:
        await state.clear()
        await message.answer(RANK_LOCKED_ALERT, reply_markup=back_to_contracts())
        return
    await state.clear()
    await message.answer(
        QUOTE_SCREEN.format(
            quantity=format_number(offer.quantity), rank=offer.rank, hours=_hours(offer.hours),
            power=format_number(offer.power * offer.quantity), total=format_number(offer.total),
            price=format_number(offer.unit_price), coins=format_number(await _coins(session, message.from_user.id)),
        ),
        reply_markup=confirm_menu(offer.rank, offer.quantity, offer.total),
    )


@router.callback_query(F.data.startswith(CB_CONTRACT_BUY_PREFIX))
async def cb_contract_buy(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    if not await _guard(callback, session):
        return
    rank, _, raw = callback.data.removeprefix(CB_CONTRACT_BUY_PREFIX).rpartition(":")
    if not raw.isdigit():
        await callback.answer()
        return
    # Popup-тексты — без HTML.
    try:
        offer = await buy(session, redis, callback.from_user.id, rank, int(raw))
    except ShopBusyError:
        await callback.answer(BUSY_ALERT)
        return
    except (RankNotAvailableError, InvalidQuantityError):
        await callback.answer(RANK_LOCKED_ALERT, show_alert=True)
        return
    except NotEnoughCoinsError as exc:
        await callback.answer(NOT_ENOUGH_ALERT.format(cost=format_number(exc.cost)), show_alert=True)
        return
    await callback.answer(
        BOUGHT_ALERT.format(quantity=format_number(offer.quantity), rank=offer.rank, hours=_hours(offer.hours)), show_alert=True
    )
    text, markup = await render_contracts(session, callback.from_user.id)
    await safe_edit_text(callback.message, text, reply_markup=markup)
