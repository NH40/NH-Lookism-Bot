"""Биржа (хендлеры): лоты, аукционы, прямой обмен, «Мои сделки» и мастер предложения.
Вход — «📈 Биржа» в магазине. `send_deal_pushes()` — публичная функция домена: пуши о
сделках, в т.ч. из фонового прохода (итоги аукционов, истёкшие обмены, `main.py`)."""
from __future__ import annotations

from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.exchange import (
    EXCHANGE_AUCTION_COMMISSION,
    EXCHANGE_AUCTION_HOURS,
    EXCHANGE_AUCTION_MIN_STEP,
    EXCHANGE_LOT_COMMISSION,
    EXCHANGE_TRADE_HOURS,
)
from bot.constant.exchange import (
    CB_EXCHANGE_AUCTION_PREFIX,
    CB_EXCHANGE_AUCTIONS_PREFIX,
    CB_EXCHANGE_BID_PREFIX,
    CB_EXCHANGE_BUY_PREFIX,
    CB_EXCHANGE_CANCEL_AUCTION_PREFIX,
    CB_EXCHANGE_CANCEL_LOT_PREFIX,
    CB_EXCHANGE_CONFIRM,
    CB_EXCHANGE_HOURS_PREFIX,
    CB_EXCHANGE_ITEM_RES_PREFIX,
    CB_EXCHANGE_ITEM_SQUAD_PREFIX,
    CB_EXCHANGE_ITEM_STATISTS,
    CB_EXCHANGE_LOT_PREFIX,
    CB_EXCHANGE_LOTS_PREFIX,
    CB_EXCHANGE_MINE,
    CB_EXCHANGE_NEW_PREFIX,
    CB_EXCHANGE_OPEN,
    CB_EXCHANGE_PRICE_RES_PREFIX,
    CB_EXCHANGE_TRADE_ACCEPT_PREFIX,
    CB_EXCHANGE_TRADE_DECLINE_PREFIX,
    MODE_AUCTION,
    MODE_LOT,
    MODE_TRADE,
)
from bot.constant.resource import ITEM_RESOURCE, ITEM_STATIST, RESOURCES
from bot.constant.settings import NOTIFY_EXCHANGE
from bot.db.repositories.user import find_by_username
from bot.keyboards.exchange import (
    auction_menu,
    auctions_menu,
    back_menu,
    confirm_menu,
    exchange_menu,
    hours_menu,
    item_menu,
    lot_menu,
    lots_menu,
    mine_menu,
    price_res_menu,
    squads_menu,
    trade_offer_menu,
)
from bot.services.exchange import (
    Deal,
    ExchangeError,
    accept_trade,
    bid,
    buy_lot,
    cancel_auction,
    cancel_lot,
    create_auction,
    create_lot,
    decline_trade,
    get_auction,
    get_lot,
    list_auctions,
    list_lots,
    list_trades,
    min_next_bid,
    mine,
    propose_trade,
)
from bot.services.extra import list_squads
from bot.services.gang import get_gang
from bot.services.resource import StatistKey, balance
from bot.services.settings import notify_player
from bot.states.exchange import ExchangeStates
from bot.texts.exchange import (
    ACCEPTED_ALERT,
    AMOUNT_PROMPT,
    AUCTION_BID_LINE,
    AUCTION_NO_BIDS,
    AUCTION_ROW,
    AUCTION_SCREEN,
    AUCTION_YOU_LEAD,
    AUCTIONS_EMPTY,
    AUCTIONS_SCREEN,
    BID_ALERT,
    BID_PROMPT,
    BOUGHT_ALERT,
    AUCTION_CANCELLED_ALERT,
    CANCELLED_ALERT,
    CONFIRM_AUCTION,
    CONFIRM_LOT,
    CONFIRM_TRADE,
    DECLINED_ALERT,
    DONE_AUCTION,
    DONE_LOT,
    DONE_TRADE,
    ERRORS,
    EXCHANGE_SCREEN,
    LOT_ROW,
    LOT_SCREEN,
    LOTS_EMPTY,
    LOTS_SCREEN,
    MINE_AUCTIONS,
    MINE_EMPTY,
    MINE_INCOMING,
    MINE_LOTS,
    MINE_OUTGOING,
    MINE_SCREEN,
    MINE_TRADE_ROW,
    NUMBER_INVALID,
    PICK_HOURS,
    PICK_ITEM,
    PICK_PRICE_RES,
    PICK_SQUAD,
    PICK_SQUAD_NONE,
    PRICE_PROMPT,
    PUSH_AUCTION_SOLD,
    PUSH_AUCTION_UNSOLD,
    PUSH_AUCTION_WON,
    PUSH_LOT_SOLD,
    PUSH_OUTBID,
    PUSH_TRADE_ACCEPTED,
    PUSH_TRADE_DECLINED,
    PUSH_TRADE_EXPIRED,
    PUSH_TRADE_OFFER,
    USERNAME_PROMPT,
    WHAT_MIN_BID,
    WHAT_MIN_BID_CAP,
    WHAT_PRICE,
    WHAT_PRICE_CAP,
    WIZARD_TITLE,
)
from bot.texts.gang import squad_title
from bot.texts.profile import NOT_ONBOARDED
from bot.texts.resource import amount_label, item_amount_label, item_label, resource_label
from bot.utils.formatting import esc, format_countdown, format_number
from bot.utils.safe_edit import safe_edit_text

router = Router(name="exchange")


def _pct(value: float) -> str:
    return f"{round(value * 100):g}"


def _left(moment: datetime) -> str:
    return format_countdown(max(0, int((moment - datetime.now(timezone.utc)).total_seconds())))


def _error(exc: ExchangeError, price_res: str = "") -> str:
    value = amount_label(price_res, exc.value) if price_res and exc.code in ("no_money", "low_bid") else exc.value
    return ERRORS[exc.code].format(value=value)


async def _guard(callback: CallbackQuery, session: AsyncSession) -> bool:
    if await get_gang(session, callback.from_user.id) is None:
        await callback.answer(NOT_ONBOARDED, show_alert=True)
        return False
    return True


async def _seller_name(session: AsyncSession, user_id: int) -> str:
    gang = await get_gang(session, user_id)
    return esc(gang.name) if gang else "—"


# --- главный экран и списки ---

@router.callback_query(F.data == CB_EXCHANGE_OPEN)
async def cb_exchange_open(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    if not await _guard(callback, session):
        return
    await callback.answer()
    text = EXCHANGE_SCREEN.format(
        lot_fee=_pct(EXCHANGE_LOT_COMMISSION), step=_pct(EXCHANGE_AUCTION_MIN_STEP), auc_fee=_pct(EXCHANGE_AUCTION_COMMISSION)
    )
    await safe_edit_text(callback.message, text, reply_markup=exchange_menu())


@router.callback_query(F.data.startswith(CB_EXCHANGE_LOTS_PREFIX))
async def cb_exchange_lots(callback: CallbackQuery, session: AsyncSession) -> None:
    raw = callback.data.removeprefix(CB_EXCHANGE_LOTS_PREFIX)
    page = int(raw) if raw.isdigit() else 0
    lots, more = await list_lots(session, callback.from_user.id, page)
    rows = "".join(
        LOT_ROW.format(id=l.id, item=item_amount_label(l.item_kind, l.item_code, l.amount), price=amount_label(l.price_res, l.price))
        for l in lots
    ) or LOTS_EMPTY
    await callback.answer()
    await safe_edit_text(callback.message, LOTS_SCREEN.format(rows=rows), reply_markup=lots_menu(lots, page, more))


@router.callback_query(F.data.startswith(CB_EXCHANGE_LOT_PREFIX))
async def cb_exchange_lot(callback: CallbackQuery, session: AsyncSession) -> None:
    raw = callback.data.removeprefix(CB_EXCHANGE_LOT_PREFIX)
    lot = await get_lot(session, int(raw)) if raw.isdigit() else None
    if lot is None:
        await callback.answer(ERRORS["gone"], show_alert=True)
        return
    await callback.answer()
    text = LOT_SCREEN.format(
        id=lot.id, item=item_amount_label(lot.item_kind, lot.item_code, lot.amount), price=amount_label(lot.price_res, lot.price),
        seller=await _seller_name(session, lot.seller_id),
    )
    await safe_edit_text(callback.message, text, reply_markup=lot_menu(lot))


@router.callback_query(F.data.startswith(CB_EXCHANGE_BUY_PREFIX))
async def cb_exchange_buy(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    raw = callback.data.removeprefix(CB_EXCHANGE_BUY_PREFIX)
    if not raw.isdigit() or not await _guard(callback, session):
        await callback.answer()
        return
    lot = await get_lot(session, int(raw))
    # Popup-тексты — без HTML.
    try:
        deal = await buy_lot(session, redis, callback.from_user.id, int(raw))
    except ExchangeError as exc:
        await callback.answer(_error(exc, lot.price_res if lot else ""), show_alert=True)
        return
    await callback.answer(BOUGHT_ALERT.format(item=item_amount_label(deal.item_kind, deal.item_code, deal.amount)), show_alert=True)
    await send_deal_pushes(callback.bot, session, [deal])
    await safe_edit_text(callback.message, EXCHANGE_SCREEN.format(
        lot_fee=_pct(EXCHANGE_LOT_COMMISSION), step=_pct(EXCHANGE_AUCTION_MIN_STEP), auc_fee=_pct(EXCHANGE_AUCTION_COMMISSION)
    ), reply_markup=exchange_menu())


def _bid_of(a) -> int:
    return a.current_bid or a.min_bid


@router.callback_query(F.data.startswith(CB_EXCHANGE_AUCTIONS_PREFIX))
async def cb_exchange_auctions(callback: CallbackQuery, session: AsyncSession) -> None:
    raw = callback.data.removeprefix(CB_EXCHANGE_AUCTIONS_PREFIX)
    page = int(raw) if raw.isdigit() else 0
    auctions, more = await list_auctions(session, callback.from_user.id, page)
    rows = "".join(
        AUCTION_ROW.format(
            id=a.id, item=item_amount_label(a.item_kind, a.item_code, a.amount), bid=amount_label(a.price_res, _bid_of(a)),
            countdown=_left(a.ends_at),
        )
        for a in auctions
    ) or AUCTIONS_EMPTY
    await callback.answer()
    await safe_edit_text(callback.message, AUCTIONS_SCREEN.format(rows=rows), reply_markup=auctions_menu(auctions, page, more, _bid_of))


async def render_auction(session: AsyncSession, user_id: int, auction_id: int):
    a = await get_auction(session, auction_id)
    if a is None:
        return None
    need = min_next_bid(a)
    bid_line = (
        AUCTION_BID_LINE.format(bid=amount_label(a.price_res, a.current_bid), you=AUCTION_YOU_LEAD if a.bidder_id == user_id else "")
        if a.current_bid
        else AUCTION_NO_BIDS.format(min_bid=amount_label(a.price_res, a.min_bid))
    )
    text = AUCTION_SCREEN.format(
        id=a.id, item=item_amount_label(a.item_kind, a.item_code, a.amount), bid_line=bid_line,
        min_next=amount_label(a.price_res, need), countdown=_left(a.ends_at),
    )
    return text, auction_menu(a, need)


@router.callback_query(F.data.startswith(CB_EXCHANGE_AUCTION_PREFIX))
async def cb_exchange_auction(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    raw = callback.data.removeprefix(CB_EXCHANGE_AUCTION_PREFIX)
    rendered = await render_auction(session, callback.from_user.id, int(raw)) if raw.isdigit() else None
    if rendered is None:
        await callback.answer(ERRORS["gone"], show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(callback.message, rendered[0], reply_markup=rendered[1])


async def _place_bid(bot: Bot, session: AsyncSession, redis: Redis, user_id: int, auction_id: int, amount: int) -> str | None:
    """→ текст ошибки или None (ставка принята, пуши отправлены)."""
    a = await get_auction(session, auction_id)
    try:
        deal = await bid(session, redis, user_id, auction_id, amount)
    except ExchangeError as exc:
        return _error(exc, a.price_res if a else "")
    await send_deal_pushes(bot, session, [deal])
    return None


@router.callback_query(F.data.startswith(CB_EXCHANGE_BID_PREFIX))
async def cb_exchange_bid(callback: CallbackQuery, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    auction_raw, _, amount_raw = callback.data.removeprefix(CB_EXCHANGE_BID_PREFIX).partition(":")
    if not (auction_raw.isdigit() and amount_raw.isdigit()) or not await _guard(callback, session):
        await callback.answer()
        return
    auction_id, amount = int(auction_raw), int(amount_raw)
    if amount == 0:
        a = await get_auction(session, auction_id)
        if a is None:
            await callback.answer(ERRORS["gone"], show_alert=True)
            return
        await state.set_state(ExchangeStates.waiting_bid)
        await state.update_data(auction_id=auction_id)
        await callback.answer()
        await safe_edit_text(callback.message, BID_PROMPT.format(id=auction_id, min_next=amount_label(a.price_res, min_next_bid(a))), reply_markup=back_menu())
        return
    error = await _place_bid(callback.bot, session, redis, callback.from_user.id, auction_id, amount)
    if error:
        await callback.answer(error, show_alert=True)
        return
    a = await get_auction(session, auction_id)
    await callback.answer(BID_ALERT.format(amount=amount_label(a.price_res, amount)) if a else "")
    rendered = await render_auction(session, callback.from_user.id, auction_id)
    if rendered:
        await safe_edit_text(callback.message, rendered[0], reply_markup=rendered[1])


def _number(text: str | None) -> int | None:
    raw = (text or "").replace(" ", "").replace("_", "")
    return int(raw) if raw.isdigit() and int(raw) > 0 else None


@router.message(ExchangeStates.waiting_bid)
async def on_exchange_bid(message: Message, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    amount = _number(message.text)
    auction_id = (await state.get_data()).get("auction_id")
    if amount is None:
        await message.answer(NUMBER_INVALID, reply_markup=back_menu())
        return
    error = await _place_bid(message.bot, session, redis, message.from_user.id, auction_id, amount)
    if error:
        await message.answer(error, reply_markup=back_menu())
        return
    await state.clear()
    rendered = await render_auction(session, message.from_user.id, auction_id)
    if rendered:
        await message.answer(rendered[0], reply_markup=rendered[1])


@router.callback_query(F.data == CB_EXCHANGE_MINE)
async def cb_exchange_mine(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    await _show_mine(callback, session)


async def _show_mine(callback: CallbackQuery, session: AsyncSession) -> None:
    user_id = callback.from_user.id
    lots, auctions = await mine(session, user_id)
    incoming, outgoing = await list_trades(session, user_id)
    parts = ""
    if lots:
        parts += MINE_LOTS.format(rows="".join(
            LOT_ROW.format(id=l.id, item=item_amount_label(l.item_kind, l.item_code, l.amount), price=amount_label(l.price_res, l.price)) for l in lots
        ))
    if auctions:
        parts += MINE_AUCTIONS.format(rows="".join(
            AUCTION_ROW.format(id=a.id, item=item_amount_label(a.item_kind, a.item_code, a.amount), bid=amount_label(a.price_res, _bid_of(a)), countdown=_left(a.ends_at))
            for a in auctions
        ))

    async def trade_rows(trades, other) -> str:
        return "".join(
            MINE_TRADE_ROW.format(
                id=t.id, item=item_amount_label(t.item_kind, t.item_code, t.amount), price=amount_label(t.price_res, t.price),
                who=await _seller_name(session, other(t)), countdown=_left(t.expires_at),
            )
            for t in trades
        )

    if incoming:
        parts += MINE_INCOMING.format(rows=await trade_rows(incoming, lambda t: t.from_id))
    if outgoing:
        parts += MINE_OUTGOING.format(rows=await trade_rows(outgoing, lambda t: t.to_id))
    text = MINE_SCREEN.format(body=parts or MINE_EMPTY)
    await safe_edit_text(callback.message, text, reply_markup=mine_menu(lots, incoming, outgoing, auctions))


@router.callback_query(F.data.startswith(CB_EXCHANGE_CANCEL_LOT_PREFIX))
async def cb_exchange_cancel_lot(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    raw = callback.data.removeprefix(CB_EXCHANGE_CANCEL_LOT_PREFIX)
    if not raw.isdigit():
        await callback.answer()
        return
    try:
        await cancel_lot(session, redis, callback.from_user.id, int(raw))
    except ExchangeError as exc:
        await callback.answer(_error(exc), show_alert=True)
        return
    await callback.answer(CANCELLED_ALERT)
    await _show_mine(callback, session)


@router.callback_query(F.data.startswith(CB_EXCHANGE_CANCEL_AUCTION_PREFIX))
async def cb_exchange_cancel_auction(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    raw = callback.data.removeprefix(CB_EXCHANGE_CANCEL_AUCTION_PREFIX)
    if not raw.isdigit():
        await callback.answer()
        return
    try:
        await cancel_auction(session, redis, callback.from_user.id, int(raw))
    except ExchangeError as exc:
        await callback.answer(_error(exc), show_alert=True)
        return
    await callback.answer(AUCTION_CANCELLED_ALERT)
    await _show_mine(callback, session)


@router.callback_query(F.data.startswith(CB_EXCHANGE_TRADE_ACCEPT_PREFIX))
async def cb_exchange_trade_accept(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    raw = callback.data.removeprefix(CB_EXCHANGE_TRADE_ACCEPT_PREFIX)
    if not raw.isdigit() or not await _guard(callback, session):
        await callback.answer()
        return
    incoming, _ = await list_trades(session, callback.from_user.id)
    trade = next((t for t in incoming if t.id == int(raw)), None)
    try:
        deal = await accept_trade(session, redis, callback.from_user.id, int(raw))
    except ExchangeError as exc:
        await callback.answer(_error(exc, trade.price_res if trade else ""), show_alert=True)
        return
    await callback.answer(ACCEPTED_ALERT.format(item=item_amount_label(deal.item_kind, deal.item_code, deal.amount)), show_alert=True)
    await send_deal_pushes(callback.bot, session, [deal])
    await _show_mine(callback, session)


@router.callback_query(F.data.startswith(CB_EXCHANGE_TRADE_DECLINE_PREFIX))
async def cb_exchange_trade_decline(callback: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    raw = callback.data.removeprefix(CB_EXCHANGE_TRADE_DECLINE_PREFIX)
    if not raw.isdigit():
        await callback.answer()
        return
    try:
        deal = await decline_trade(session, redis, callback.from_user.id, int(raw))
    except ExchangeError as exc:
        await callback.answer(_error(exc), show_alert=True)
        return
    await callback.answer(DECLINED_ALERT)
    if deal.buyer_id == callback.from_user.id:  # отказал получатель — сказать автору
        await send_deal_pushes(callback.bot, session, [deal])
    await _show_mine(callback, session)


# --- мастер предложения ---

async def _title(state: FSMContext) -> str:
    return WIZARD_TITLE.get((await state.get_data()).get("mode", MODE_LOT), "")


async def _summary(state: FSMContext) -> tuple[str, str]:
    """(предмет с количеством, цена) из собранных данных мастера."""
    data = await state.get_data()
    item = item_amount_label(data["item_kind"], data["item_code"], data["amount"]) if "amount" in data else ""
    price = amount_label(data["price_res"], data["price"]) if "price" in data else ""
    return item, price


@router.callback_query(F.data.startswith(CB_EXCHANGE_NEW_PREFIX))
async def cb_exchange_new(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    mode = callback.data.removeprefix(CB_EXCHANGE_NEW_PREFIX)
    if mode not in WIZARD_TITLE or not await _guard(callback, session):
        await callback.answer()
        return
    await state.clear()
    await state.update_data(mode=mode)
    await callback.answer()
    await safe_edit_text(callback.message, PICK_ITEM.format(title=WIZARD_TITLE[mode]), reply_markup=item_menu())


async def _ask_amount(callback: CallbackQuery, state: FSMContext, kind: str, code: str, have: int) -> None:
    await state.update_data(item_kind=kind, item_code=code)
    await state.set_state(ExchangeStates.waiting_amount)
    await callback.answer()
    await safe_edit_text(
        callback.message, AMOUNT_PROMPT.format(title=await _title(state), item=item_label(kind, code), have=format_number(have)),
        reply_markup=back_menu(),
    )


@router.callback_query(F.data.startswith(CB_EXCHANGE_ITEM_RES_PREFIX))
async def cb_exchange_item_res(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    code = callback.data.removeprefix(CB_EXCHANGE_ITEM_RES_PREFIX)
    if code not in RESOURCES:
        await callback.answer()
        return
    await _ask_amount(callback, state, ITEM_RESOURCE, code, await balance(session, callback.from_user.id, code))


async def _squads(session: AsyncSession, user_id: int) -> list[tuple[str, str, int]]:
    return [
        (
            StatistKey(sq.rank, sq.stars, sq.training_level, sq.school, sq.school_level).encode(),
            squad_title(sq.rank, sq.stars, sq.training_level, sq.school, sq.school_level),
            sq.attack + sq.defense,
        )
        for sq in await list_squads(session, user_id)
        if sq.attack + sq.defense > 0
    ]


@router.callback_query(F.data == CB_EXCHANGE_ITEM_STATISTS)
async def cb_exchange_item_statists(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    squads = await _squads(session, callback.from_user.id)
    if not squads:
        await callback.answer(PICK_SQUAD_NONE, show_alert=True)
        return
    await callback.answer()
    await safe_edit_text(callback.message, PICK_SQUAD.format(title=await _title(state)), reply_markup=squads_menu(squads))


@router.callback_query(F.data.startswith(CB_EXCHANGE_ITEM_SQUAD_PREFIX))
async def cb_exchange_item_squad(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    code = callback.data.removeprefix(CB_EXCHANGE_ITEM_SQUAD_PREFIX)
    squad = next((s for s in await _squads(session, callback.from_user.id) if s[0] == code), None)
    if squad is None:
        await callback.answer()
        return
    await _ask_amount(callback, state, ITEM_STATIST, code, squad[2])


@router.message(ExchangeStates.waiting_amount)
async def on_exchange_amount(message: Message, state: FSMContext) -> None:
    amount = _number(message.text)
    if amount is None:
        await message.answer(NUMBER_INVALID, reply_markup=back_menu())
        return
    await state.update_data(amount=amount)
    await state.set_state(None)
    data = await state.get_data()
    item, _ = await _summary(state)
    what = WHAT_MIN_BID if data.get("mode") == MODE_AUCTION else WHAT_PRICE
    await message.answer(PICK_PRICE_RES.format(title=await _title(state), amount=item, what=what), reply_markup=price_res_menu())


@router.callback_query(F.data.startswith(CB_EXCHANGE_PRICE_RES_PREFIX))
async def cb_exchange_price_res(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data.removeprefix(CB_EXCHANGE_PRICE_RES_PREFIX)
    data = await state.get_data()
    if code not in RESOURCES or "amount" not in data:
        await callback.answer()
        return
    await state.update_data(price_res=code)
    await state.set_state(ExchangeStates.waiting_price)
    item, _ = await _summary(state)
    what = WHAT_MIN_BID_CAP if data.get("mode") == MODE_AUCTION else WHAT_PRICE_CAP
    await callback.answer()
    await safe_edit_text(
        callback.message, PRICE_PROMPT.format(title=await _title(state), amount=item, what_cap=what, res=resource_label(code)),
        reply_markup=back_menu(),
    )


async def _confirm_text(state: FSMContext) -> str:
    data = await state.get_data()
    item, price = await _summary(state)
    title = await _title(state)
    if data["mode"] == MODE_AUCTION:
        return CONFIRM_AUCTION.format(title=title, amount=item, price=price, hours=data["hours"], fee=_pct(EXCHANGE_AUCTION_COMMISSION))
    if data["mode"] == MODE_TRADE:
        return CONFIRM_TRADE.format(title=title, amount=item, price=price, target=esc("@" + data["target"]), hours=EXCHANGE_TRADE_HOURS)
    return CONFIRM_LOT.format(title=title, amount=item, price=price, fee=_pct(EXCHANGE_LOT_COMMISSION))


@router.message(ExchangeStates.waiting_price)
async def on_exchange_price(message: Message, state: FSMContext) -> None:
    price = _number(message.text)
    if price is None:
        await message.answer(NUMBER_INVALID, reply_markup=back_menu())
        return
    await state.update_data(price=price)
    await state.set_state(None)
    data = await state.get_data()
    item, price_label = await _summary(state)
    title = await _title(state)
    if data["mode"] == MODE_AUCTION:
        await message.answer(PICK_HOURS.format(title=title, amount=item, price=price_label), reply_markup=hours_menu())
    elif data["mode"] == MODE_TRADE:
        await state.set_state(ExchangeStates.waiting_username)
        await message.answer(USERNAME_PROMPT.format(title=title, amount=item, price=price_label), reply_markup=back_menu())
    else:
        await message.answer(await _confirm_text(state), reply_markup=confirm_menu())


@router.callback_query(F.data.startswith(CB_EXCHANGE_HOURS_PREFIX))
async def cb_exchange_hours(callback: CallbackQuery, state: FSMContext) -> None:
    raw = callback.data.removeprefix(CB_EXCHANGE_HOURS_PREFIX)
    data = await state.get_data()
    if not raw.isdigit() or int(raw) not in EXCHANGE_AUCTION_HOURS or "price" not in data:
        await callback.answer()
        return
    await state.update_data(hours=int(raw))
    await callback.answer()
    await safe_edit_text(callback.message, await _confirm_text(state), reply_markup=confirm_menu())


@router.message(ExchangeStates.waiting_username)
async def on_exchange_username(message: Message, state: FSMContext, session: AsyncSession) -> None:
    username = (message.text or "").strip().lstrip("@")
    target = await find_by_username(session, username) if username else None
    if target is None or target.id == message.from_user.id:
        await message.answer(ERRORS["no_player"] if target is None else ERRORS["own"], reply_markup=back_menu())
        return
    await state.update_data(target=username)
    await state.set_state(None)
    await message.answer(await _confirm_text(state), reply_markup=confirm_menu())


@router.callback_query(F.data == CB_EXCHANGE_CONFIRM)
async def cb_exchange_confirm(callback: CallbackQuery, state: FSMContext, session: AsyncSession, redis: Redis) -> None:
    data = await state.get_data()
    needed = {"mode", "item_kind", "item_code", "amount", "price_res", "price"}
    if not needed <= data.keys() or not await _guard(callback, session):
        await callback.answer()
        return
    user_id = callback.from_user.id
    args = (data["item_kind"], data["item_code"], data["amount"], data["price_res"], data["price"])
    # Popup-тексты — без HTML.
    try:
        if data["mode"] == MODE_AUCTION:
            new_id = await create_auction(session, redis, user_id, *args, data.get("hours", 0))
            done = DONE_AUCTION.format(id=new_id)
        elif data["mode"] == MODE_TRADE:
            new_id, target_id = await propose_trade(session, redis, user_id, data.get("target", ""), *args)
            done = DONE_TRADE.format(id=new_id)
            await notify_player(
                callback.bot, session, target_id, NOTIFY_EXCHANGE,
                PUSH_TRADE_OFFER.format(
                    id=new_id, item=item_amount_label(data["item_kind"], data["item_code"], data["amount"]),
                    price=amount_label(data["price_res"], data["price"]), from_name=await _seller_name(session, user_id),
                ),
                reply_markup=trade_offer_menu(new_id),
            )
        else:
            new_id = await create_lot(session, redis, user_id, *args)
            done = DONE_LOT.format(id=new_id)
    except ExchangeError as exc:
        await callback.answer(_error(exc, data["price_res"]), show_alert=True)
        return
    await state.clear()
    await callback.answer()
    await safe_edit_text(callback.message, done, reply_markup=exchange_menu())


# --- пуши ---

async def send_deal_pushes(bot: Bot, session: AsyncSession, deals: list[Deal]) -> None:
    for d in deals:
        item = item_amount_label(d.item_kind, d.item_code, d.amount)
        price = amount_label(d.price_res, d.price)
        pushes: list[tuple[int, str]] = []
        if d.kind == "lot":
            pushes.append((d.seller_id, PUSH_LOT_SOLD.format(item=item, price=price, fee=_pct(EXCHANGE_LOT_COMMISSION))))
        elif d.kind == "bid" and d.previous_bidder:
            pushes.append((d.previous_bidder, PUSH_OUTBID.format(bid=amount_label(d.price_res, d.previous_bid))))
        elif d.kind == "auction_sold":
            pushes.append((d.buyer_id, PUSH_AUCTION_WON.format(item=item, price=price)))
            pushes.append((d.seller_id, PUSH_AUCTION_SOLD.format(item=item, price=price, fee=_pct(EXCHANGE_AUCTION_COMMISSION))))
        elif d.kind == "auction_unsold":
            pushes.append((d.seller_id, PUSH_AUCTION_UNSOLD.format(item=item)))
        elif d.kind == "trade":
            pushes.append((d.seller_id, PUSH_TRADE_ACCEPTED.format(item=item, price=price)))
        elif d.kind == "trade_declined":
            pushes.append((d.seller_id, PUSH_TRADE_DECLINED.format(item=item)))
        elif d.kind == "trade_expired":
            pushes.append((d.seller_id, PUSH_TRADE_EXPIRED.format(item=item)))
        for user_id, text in pushes:
            await notify_player(bot, session, user_id, NOTIFY_EXCHANGE, text)
