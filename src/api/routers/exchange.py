"""API-роутер Mini App: биржа — лоты, аукционы, прямой обмен, мои.

Только `bot.services.exchange` (те же функции, что вызывает хендлер бота). Пуши второй
стороне шлёт `api.push` теми же функциями/текстами, что хендлер бота.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.deps import get_redis
from api.push import push, with_bot_session
from api.routers._common import bad, clean_label, require_user
from bot.config.exchange import (
    EXCHANGE_AUCTION_COMMISSION,
    EXCHANGE_AUCTION_HOURS,
    EXCHANGE_AUCTION_MIN_STEP,
    EXCHANGE_LOT_COMMISSION,
    EXCHANGE_MAX_AUCTIONS,
    EXCHANGE_MAX_LOTS,
    EXCHANGE_MAX_TRADES,
    EXCHANGE_TRADE_HOURS,
)
from bot.constant.resource import ITEM_STATIST, RESOURCES
from bot.constant.settings import NOTIFY_EXCHANGE
from bot.db.models.gang import Gang
from bot.handlers.exchange.exchange import send_deal_pushes
from bot.keyboards.exchange import trade_offer_menu
from bot.services import exchange as svc
from bot.services.exchange import ExchangeError
from bot.services.extra import list_squads
from bot.services.gang import get_gang
from bot.services.resource import StatistKey, balances
from bot.texts.exchange import (
    PUSH_TRADE_OFFER,
    ACCEPTED_ALERT,
    BID_ALERT,
    BOUGHT_ALERT,
    AUCTION_CANCELLED_ALERT,
    CANCELLED_ALERT,
    DECLINED_ALERT,
    ERRORS,
)
from bot.texts.resource import RESOURCE_NAMES, amount_label, item_amount_label, item_label
from bot.utils.formatting import esc, format_number

router = APIRouter(prefix="/api/exchange", tags=["exchange"])

_ERROR_FALLBACK = "Не получилось."


def _err(exc: ExchangeError):
    text = ERRORS.get(exc.code, _ERROR_FALLBACK).format(value=format_number(exc.value))
    return bad(text)


def _plain(text: str) -> str:
    return clean_label(text).replace("⭐", "★")


class ItemOut(BaseModel):
    kind: str
    code: str
    amount: int
    label: str  # «NHCoin» / «C ★1»
    full: str  # «1 500 NHCoin»


class LotOut(BaseModel):
    id: int
    seller: str
    item: ItemOut
    price_res: str
    price_label: str
    price: int
    price_full: str


class AuctionOut(BaseModel):
    id: int
    seller: str
    item: ItemOut
    price_res: str
    price_label: str
    min_bid: int
    current_bid: int
    next_bid: int
    leading: bool  # лидер — сам игрок
    mine: bool
    seconds_left: int
    price_full: str


class TradeOut(BaseModel):
    id: int
    other: str  # второй участник
    item: ItemOut
    price_res: str
    price_label: str
    price: int
    price_full: str
    seconds_left: int


class ResourceOpt(BaseModel):
    code: str
    label: str
    balance: int


class SquadOpt(BaseModel):
    code: str
    label: str
    total: int


class ConfigOut(BaseModel):
    lot_commission: float
    auction_commission: float
    auction_min_step: float
    auction_hours: list[int]
    max_lots: int
    max_auctions: int
    max_trades: int
    trade_hours: int
    resources: list[ResourceOpt]
    squads: list[SquadOpt]


class ExchangeOut(BaseModel):
    lots: list[LotOut]
    lots_has_more: bool
    auctions: list[AuctionOut]
    auctions_has_more: bool
    incoming: list[TradeOut]
    outgoing: list[TradeOut]
    my_lots: list[LotOut]
    my_auctions: list[AuctionOut]
    config: ConfigOut


def _seconds_left(moment: datetime) -> int:
    return max(0, int((moment - datetime.now(timezone.utc)).total_seconds()))


def _item(kind: str, code: str, amount: int) -> ItemOut:
    return ItemOut(kind=kind, code=code, amount=amount, label=_plain(item_label(kind, code)),
                   full=_plain(item_amount_label(kind, code, amount)))


def _price_label(res: str) -> str:
    return RESOURCE_NAMES.get(res, res)


async def _names(session: AsyncSession, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    rows = await session.execute(select(Gang.user_id, Gang.name).where(Gang.user_id.in_(ids)))
    return dict(rows.all())


def _lot(lot, names: dict[int, str]) -> LotOut:
    return LotOut(
        id=lot.id, seller=names.get(lot.seller_id, "—"), item=_item(lot.item_kind, lot.item_code, lot.amount),
        price_res=lot.price_res, price_label=_price_label(lot.price_res), price=lot.price,
        price_full=f"{format_number(lot.price)} {_price_label(lot.price_res)}",
    )


def _auction(a, names: dict[int, str], user_id: int) -> AuctionOut:
    return AuctionOut(
        id=a.id, seller=names.get(a.seller_id, "—"), item=_item(a.item_kind, a.item_code, a.amount),
        price_res=a.price_res, price_label=_price_label(a.price_res), min_bid=a.min_bid, current_bid=a.current_bid,
        next_bid=svc.min_next_bid(a), leading=a.bidder_id == user_id, mine=a.seller_id == user_id,
        seconds_left=_seconds_left(a.ends_at),
        price_full=f"{format_number(a.current_bid or a.min_bid)} {_price_label(a.price_res)}",
    )


def _trade(t, names: dict[int, str], other_id: int) -> TradeOut:
    return TradeOut(
        id=t.id, other=names.get(other_id, "—"), item=_item(t.item_kind, t.item_code, t.amount),
        price_res=t.price_res, price_label=_price_label(t.price_res), price=t.price,
        price_full=f"{format_number(t.price)} {_price_label(t.price_res)}", seconds_left=_seconds_left(t.expires_at),
    )


@router.get("", response_model=ExchangeOut)
async def get_exchange(
    lot_page: int = Query(0, ge=0, le=1000),
    auction_page: int = Query(0, ge=0, le=1000),
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ExchangeOut:
    await require_user(session, user_id)
    lots, lots_more = await svc.list_lots(session, user_id, lot_page)
    auctions, auctions_more = await svc.list_auctions(session, user_id, auction_page)
    incoming, outgoing = await svc.list_trades(session, user_id)
    my_lots, my_auctions = await svc.mine(session, user_id)
    ids: set[int] = {user_id}
    ids |= {x.seller_id for x in (*lots, *auctions)}
    ids |= {t.from_id for t in incoming} | {t.to_id for t in outgoing}
    names = await _names(session, ids)
    bal = await balances(session, user_id)
    squads = await list_squads(session, user_id)
    squad_opts = [
        SquadOpt(
            code=StatistKey(s.rank, s.stars, s.training_level, s.school, s.school_level).encode(),
            label=_plain(item_label(ITEM_STATIST, StatistKey(s.rank, s.stars, s.training_level, s.school, s.school_level).encode())),
            total=s.attack + s.defense,
        )
        for s in squads if s.attack + s.defense > 0
    ]
    return ExchangeOut(
        lots=[_lot(x, names) for x in lots], lots_has_more=lots_more,
        auctions=[_auction(x, names, user_id) for x in auctions], auctions_has_more=auctions_more,
        incoming=[_trade(t, names, t.from_id) for t in incoming],
        outgoing=[_trade(t, names, t.to_id) for t in outgoing],
        my_lots=[_lot(x, names) for x in my_lots], my_auctions=[_auction(x, names, user_id) for x in my_auctions],
        config=ConfigOut(
            lot_commission=EXCHANGE_LOT_COMMISSION, auction_commission=EXCHANGE_AUCTION_COMMISSION,
            auction_min_step=EXCHANGE_AUCTION_MIN_STEP, auction_hours=list(EXCHANGE_AUCTION_HOURS),
            max_lots=EXCHANGE_MAX_LOTS, max_auctions=EXCHANGE_MAX_AUCTIONS, max_trades=EXCHANGE_MAX_TRADES,
            trade_hours=EXCHANGE_TRADE_HOURS,
            resources=[ResourceOpt(code=c, label=_price_label(c), balance=bal.get(c, 0)) for c in RESOURCES],
            squads=squad_opts,
        ),
    )


class IdIn(BaseModel):
    id: int


class BidIn(BaseModel):
    id: int
    amount: int = Field(gt=0)


class OfferIn(BaseModel):
    item_kind: Literal["res", "statist"]
    item_code: str = Field(min_length=1, max_length=64)
    amount: int = Field(gt=0)
    price_res: str
    price: int = Field(gt=0)


class AuctionIn(BaseModel):
    item_kind: Literal["res", "statist"]
    item_code: str = Field(min_length=1, max_length=64)
    amount: int = Field(gt=0)
    price_res: str
    min_bid: int = Field(gt=0)
    hours: int


class TradeIn(OfferIn):
    username: str = Field(min_length=1, max_length=40)


@router.post("/lots/buy")
async def buy_lot(body: IdIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                  redis: Redis = Depends(get_redis)) -> dict:
    await require_user(session, user_id)
    try:
        deal = await svc.buy_lot(session, redis, user_id, body.id)
    except ExchangeError as exc:
        raise _err(exc) from exc
    await with_bot_session(lambda bot, s: send_deal_pushes(bot, s, [deal]))
    return {"message": BOUGHT_ALERT.format(item=_plain(item_amount_label(deal.item_kind, deal.item_code, deal.amount)))}


@router.post("/lots/create")
async def create_lot(body: OfferIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                     redis: Redis = Depends(get_redis)) -> dict:
    await require_user(session, user_id)
    try:
        await svc.create_lot(session, redis, user_id, body.item_kind, body.item_code, body.amount, body.price_res, body.price)
    except ExchangeError as exc:
        raise _err(exc) from exc
    return {"message": "Лот выставлен"}


@router.post("/auctions/cancel")
async def cancel_auction(body: IdIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                         redis: Redis = Depends(get_redis)) -> dict:
    await require_user(session, user_id)
    try:
        await svc.cancel_auction(session, redis, user_id, body.id)
    except ExchangeError as exc:
        raise _err(exc) from exc
    return {"message": AUCTION_CANCELLED_ALERT}


@router.post("/lots/cancel")
async def cancel_lot(body: IdIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                     redis: Redis = Depends(get_redis)) -> dict:
    await require_user(session, user_id)
    try:
        await svc.cancel_lot(session, redis, user_id, body.id)
    except ExchangeError as exc:
        raise _err(exc) from exc
    return {"message": CANCELLED_ALERT}


@router.post("/auctions/bid")
async def bid(body: BidIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
              redis: Redis = Depends(get_redis)) -> dict:
    await require_user(session, user_id)
    try:
        deal = await svc.bid(session, redis, user_id, body.id, body.amount)
    except ExchangeError as exc:
        raise _err(exc) from exc
    await with_bot_session(lambda bot, s: send_deal_pushes(bot, s, [deal]))
    return {"message": BID_ALERT.format(amount=format_number(body.amount))}


@router.post("/auctions/create")
async def create_auction(body: AuctionIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                         redis: Redis = Depends(get_redis)) -> dict:
    await require_user(session, user_id)
    try:
        await svc.create_auction(session, redis, user_id, body.item_kind, body.item_code, body.amount, body.price_res,
                                 body.min_bid, body.hours)
    except ExchangeError as exc:
        raise _err(exc) from exc
    return {"message": "Аукцион запущен"}


@router.post("/trades/propose")
async def propose(body: TradeIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                  redis: Redis = Depends(get_redis)) -> dict:
    await require_user(session, user_id)
    try:
        new_id, target_id = await svc.propose_trade(session, redis, user_id, body.username, body.item_kind,
                                                    body.item_code, body.amount, body.price_res, body.price)
    except ExchangeError as exc:
        raise _err(exc) from exc
    gang = await get_gang(session, user_id)
    await push(
        target_id, NOTIFY_EXCHANGE,
        PUSH_TRADE_OFFER.format(
            id=new_id, item=item_amount_label(body.item_kind, body.item_code, body.amount),
            price=amount_label(body.price_res, body.price), from_name=esc(gang.name) if gang else "—",
        ),
        reply_markup=trade_offer_menu(new_id),
    )
    return {"message": "Предложение отправлено"}


@router.post("/trades/accept")
async def accept(body: IdIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                 redis: Redis = Depends(get_redis)) -> dict:
    await require_user(session, user_id)
    try:
        deal = await svc.accept_trade(session, redis, user_id, body.id)
    except ExchangeError as exc:
        raise _err(exc) from exc
    await with_bot_session(lambda bot, s: send_deal_pushes(bot, s, [deal]))
    return {"message": ACCEPTED_ALERT.format(item=_plain(item_amount_label(deal.item_kind, deal.item_code, deal.amount)))}


@router.post("/trades/decline")
async def decline(body: IdIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                  redis: Redis = Depends(get_redis)) -> dict:
    await require_user(session, user_id)
    try:
        deal = await svc.decline_trade(session, redis, user_id, body.id)
    except ExchangeError as exc:
        raise _err(exc) from exc
    if deal.buyer_id == user_id:  # отказал получатель — сказать автору
        await with_bot_session(lambda bot, s: send_deal_pushes(bot, s, [deal]))
    return {"message": DECLINED_ALERT}
