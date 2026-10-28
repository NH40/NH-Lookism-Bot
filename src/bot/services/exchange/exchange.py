"""Биржа — лоты, аукционы, прямой обмен (сервис). Перенос из 1.0 («Рынок»), дизайн —
`config/exchange`.

Предмет (ресурс или отряд статистов) уходит в залог при выставлении — на балансе его нет,
отменили — вернулся. Деньги покупателя/ставка — тоже атомарно через реестр ресурсов. Строки
сделок берутся `FOR UPDATE` (двойной клик и два покупателя одного лота не купят дважды),
лок на клик (правило 2), один commit на сделку (правило 10). Комиссия продавца уходит из
экономики. Сгорает залог вместе с прогрессом (пробуждение, удаление банды).
"""
from __future__ import annotations

from bot.services.build import get_build
from bot.constant.dev_quest import TASK_EXCHANGE_DEAL, TASK_EXCHANGE_LIST

from bot.services.dev_quest import emit as quest_event

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.cache.keys import action_lock
from bot.config.exchange import (
    EXCHANGE_AUCTION_COMMISSION,
    EXCHANGE_AUCTION_EXTEND_SECONDS,
    EXCHANGE_AUCTION_HOURS,
    EXCHANGE_AUCTION_MIN_STEP,
    EXCHANGE_AUCTION_SOFT_CLOSE_SECONDS,
    EXCHANGE_LOT_COMMISSION,
    EXCHANGE_MAX_AUCTIONS,
    EXCHANGE_MAX_LOTS,
    EXCHANGE_MAX_TRADES,
    EXCHANGE_PAGE,
    EXCHANGE_TRADE_HOURS,
)
from bot.config.game import ACTION_LOCK_MS
from bot.constant.exchange import LOCK_ACTION_EXCHANGE
from bot.constant.resource import ITEM_RESOURCE, RES_DONATE, RESOURCES
from bot.db.models.exchange import ExchangeAuction, ExchangeLot, ExchangeTrade
from bot.db.repositories.user import find_by_username
from bot.services.resource import InvalidItemError, check_item, give_item, grant, spend, take_item


class ExchangeError(Exception):
    """Ошибка сделки — код текста (`texts/exchange.ERRORS`)."""

    def __init__(self, code: str, value: int = 0) -> None:
        super().__init__(code)
        self.code, self.value = code, value


@dataclass(frozen=True, slots=True)
class Deal:
    """Итог сделки — кого и о чём уведомить."""

    kind: str
    item_kind: str
    item_code: str
    amount: int
    price_res: str
    price: int
    seller_id: int = 0
    buyer_id: int = 0
    previous_bidder: int = 0
    previous_bid: int = 0


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _lock(redis: Redis, user_id: int) -> str:
    key = action_lock(user_id, LOCK_ACTION_EXCHANGE)
    if not await redis.set(key, "1", nx=True, px=ACTION_LOCK_MS):
        raise ExchangeError("busy")
    return key


def _check_offer(item_kind: str, item_code: str, amount: int, price_res: str, price: int) -> None:
    try:
        check_item(item_kind, item_code, amount)
    except InvalidItemError as exc:
        raise ExchangeError("bad_item") from exc
    if price_res not in RESOURCES or price <= 0:
        raise ExchangeError("bad_price")


async def _count(session: AsyncSession, model, column, user_id: int) -> int:
    return int(await session.scalar(select(func.count()).select_from(model).where(column == user_id)) or 0)


# --- лоты ---

async def list_lots(session: AsyncSession, viewer_id: int, page: int = 0) -> tuple[list[ExchangeLot], bool]:
    rows = (
        await session.scalars(
            select(ExchangeLot).where(ExchangeLot.seller_id != viewer_id)
            .order_by(ExchangeLot.created_at.desc()).offset(page * EXCHANGE_PAGE).limit(EXCHANGE_PAGE + 1)
        )
    ).all()
    return list(rows[:EXCHANGE_PAGE]), len(rows) > EXCHANGE_PAGE


async def get_lot(session: AsyncSession, lot_id: int) -> ExchangeLot | None:
    return await session.get(ExchangeLot, lot_id, populate_existing=True)


async def create_lot(session: AsyncSession, redis: Redis, user_id: int, item_kind: str, item_code: str, amount: int,
                     price_res: str, price: int) -> int:
    _check_offer(item_kind, item_code, amount, price_res, price)
    key = await _lock(redis, user_id)
    try:
        if await _count(session, ExchangeLot, ExchangeLot.seller_id, user_id) >= EXCHANGE_MAX_LOTS:
            raise ExchangeError("too_many_lots", EXCHANGE_MAX_LOTS)
        if not await take_item(session, user_id, item_kind, item_code, amount):
            raise ExchangeError("not_enough")
        lot = ExchangeLot(seller_id=user_id, item_kind=item_kind, item_code=item_code, amount=amount, price_res=price_res, price=price)
        session.add(lot)
        await session.flush()
        lot_id = lot.id
        await quest_event(session, user_id, TASK_EXCHANGE_LIST)
        await session.commit()
        return lot_id
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


async def cancel_lot(session: AsyncSession, redis: Redis, user_id: int, lot_id: int) -> None:
    key = await _lock(redis, user_id)
    try:
        lot = await session.scalar(select(ExchangeLot).where(ExchangeLot.id == lot_id, ExchangeLot.seller_id == user_id).with_for_update())
        if lot is None:
            raise ExchangeError("gone")
        await give_item(session, user_id, lot.item_kind, lot.item_code, lot.amount)
        await session.execute(delete(ExchangeLot).where(ExchangeLot.id == lot.id))
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


async def cancel_auction(session: AsyncSession, redis: Redis, user_id: int, auction_id: int) -> None:
    """Снять свой аукцион — только пока на нём нет ни одной ставки (иначе у ставившего
    отобрали бы уже зарезервированные деньги и лидерство). Предмет возвращается продавцу."""
    key = await _lock(redis, user_id)
    try:
        auction = await session.scalar(
            select(ExchangeAuction).where(ExchangeAuction.id == auction_id, ExchangeAuction.seller_id == user_id).with_for_update()
        )
        if auction is None:
            raise ExchangeError("gone")
        if auction.bidder_id is not None:
            raise ExchangeError("has_bids")
        await give_item(session, user_id, auction.item_kind, auction.item_code, auction.amount)
        await session.execute(delete(ExchangeAuction).where(ExchangeAuction.id == auction.id))
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


async def buy_lot(session: AsyncSession, redis: Redis, buyer_id: int, lot_id: int) -> Deal:
    key = await _lock(redis, buyer_id)
    try:
        lot = await session.scalar(select(ExchangeLot).where(ExchangeLot.id == lot_id).with_for_update())
        if lot is None:
            raise ExchangeError("gone")
        if lot.seller_id == buyer_id:
            raise ExchangeError("own")
        if not await spend(session, buyer_id, lot.price_res, lot.price):
            raise ExchangeError("no_money", lot.price)
        await grant(session, lot.seller_id, lot.price_res, lot.price - int(lot.price * EXCHANGE_LOT_COMMISSION))
        await give_item(session, buyer_id, lot.item_kind, lot.item_code, lot.amount)
        deal = Deal("lot", lot.item_kind, lot.item_code, lot.amount, lot.price_res, lot.price, lot.seller_id, buyer_id)
        await session.execute(delete(ExchangeLot).where(ExchangeLot.id == lot.id))
        await quest_event(session, buyer_id, TASK_EXCHANGE_DEAL)
        await session.commit()
        return deal
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


# --- аукционы ---

def min_next_bid(auction: ExchangeAuction) -> int:
    if not auction.current_bid:
        return auction.min_bid
    return auction.current_bid + max(1, int(auction.current_bid * EXCHANGE_AUCTION_MIN_STEP))


async def list_auctions(session: AsyncSession, viewer_id: int, page: int = 0) -> tuple[list[ExchangeAuction], bool]:
    rows = (
        await session.scalars(
            select(ExchangeAuction).where(ExchangeAuction.seller_id != viewer_id, ExchangeAuction.ends_at > _now())
            .order_by(ExchangeAuction.ends_at).offset(page * EXCHANGE_PAGE).limit(EXCHANGE_PAGE + 1)
        )
    ).all()
    return list(rows[:EXCHANGE_PAGE]), len(rows) > EXCHANGE_PAGE


async def get_auction(session: AsyncSession, auction_id: int) -> ExchangeAuction | None:
    return await session.get(ExchangeAuction, auction_id, populate_existing=True)


async def create_auction(session: AsyncSession, redis: Redis, user_id: int, item_kind: str, item_code: str, amount: int,
                         price_res: str, min_bid: int, hours: int) -> int:
    _check_offer(item_kind, item_code, amount, price_res, min_bid)
    # Донат-коины на аукционе запрещены — и лотом, и ценой (пользователь 2026-10-28).
    if price_res == RES_DONATE or (item_kind == ITEM_RESOURCE and item_code == RES_DONATE):
        raise ExchangeError("no_donate_auction")
    if hours not in EXCHANGE_AUCTION_HOURS:
        raise ExchangeError("bad_hours")
    key = await _lock(redis, user_id)
    try:
        if await _count(session, ExchangeAuction, ExchangeAuction.seller_id, user_id) >= EXCHANGE_MAX_AUCTIONS:
            raise ExchangeError("too_many_auctions", EXCHANGE_MAX_AUCTIONS)
        if not await take_item(session, user_id, item_kind, item_code, amount):
            raise ExchangeError("not_enough")
        auction = ExchangeAuction(
            seller_id=user_id, item_kind=item_kind, item_code=item_code, amount=amount, price_res=price_res,
            min_bid=min_bid, ends_at=_now() + timedelta(hours=hours),
        )
        session.add(auction)
        await session.flush()
        auction_id = auction.id
        await quest_event(session, user_id, TASK_EXCHANGE_LIST)
        await session.commit()
        return auction_id
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


async def bid(session: AsyncSession, redis: Redis, user_id: int, auction_id: int, amount: int) -> Deal:
    """Ставка: новая ставка в залог, прежнему лидеру его ставка возвращается; ставка в последнюю
    минуту продлевает аукцион (антиснайп из 1.0). Своя ставка поверх своей — доплата разницы."""
    key = await _lock(redis, user_id)
    try:
        auction = await session.scalar(select(ExchangeAuction).where(ExchangeAuction.id == auction_id).with_for_update())
        now = _now()
        if auction is None or auction.ends_at <= now:
            raise ExchangeError("gone")
        if auction.seller_id == user_id:
            raise ExchangeError("own")
        need = min_next_bid(auction)
        if amount < need:
            raise ExchangeError("low_bid", need)
        previous, previous_bid = auction.bidder_id, auction.current_bid
        charge = amount - previous_bid if previous == user_id else amount
        if not await spend(session, user_id, auction.price_res, charge):
            raise ExchangeError("no_money", charge)
        if previous and previous != user_id:
            await grant(session, previous, auction.price_res, previous_bid)
        auction.current_bid, auction.bidder_id = amount, user_id
        if (auction.ends_at - now).total_seconds() < EXCHANGE_AUCTION_SOFT_CLOSE_SECONDS:
            auction.ends_at = now + timedelta(seconds=EXCHANGE_AUCTION_EXTEND_SECONDS)
        deal = Deal(
            "bid", auction.item_kind, auction.item_code, auction.amount, auction.price_res, amount, auction.seller_id, user_id,
            previous if previous != user_id else 0, previous_bid,
        )
        await session.commit()
        return deal
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


async def finish_auctions(session_factory: async_sessionmaker[AsyncSession]) -> list[Deal]:
    """Фоновый проход: завершить истёкшие аукционы. Есть ставка — предмет лидеру, продавцу
    ставка минус комиссия; нет — предмет назад продавцу. Каждый аукцион — своя транзакция."""
    async with session_factory() as session:
        due = list((await session.scalars(select(ExchangeAuction.id).where(ExchangeAuction.ends_at <= _now()))).all())
    deals = []
    for auction_id in due:
        async with session_factory() as session:
            a = await session.scalar(select(ExchangeAuction).where(ExchangeAuction.id == auction_id).with_for_update())
            if a is None or a.ends_at > _now():
                continue
            if a.bidder_id and a.current_bid:
                await give_item(session, a.bidder_id, a.item_kind, a.item_code, a.amount)
                await quest_event(session, a.bidder_id, TASK_EXCHANGE_DEAL)
                # «Брокер» продавца (Бизнесмен): комиссия аукциона меньше.
                seller_pos = (await get_build(session, a.seller_id)).positions
                fee = EXCHANGE_AUCTION_COMMISSION * (1 - min(0.8, seller_pos.get("exchange_fee"))) if seller_pos is not None else EXCHANGE_AUCTION_COMMISSION
                await grant(session, a.seller_id, a.price_res, a.current_bid - int(a.current_bid * fee))
                deals.append(Deal("auction_sold", a.item_kind, a.item_code, a.amount, a.price_res, a.current_bid, a.seller_id, a.bidder_id))
            else:
                await give_item(session, a.seller_id, a.item_kind, a.item_code, a.amount)
                deals.append(Deal("auction_unsold", a.item_kind, a.item_code, a.amount, a.price_res, 0, a.seller_id))
            await session.execute(delete(ExchangeAuction).where(ExchangeAuction.id == a.id))
            await session.commit()
    return deals


# --- прямой обмен ---

async def propose_trade(session: AsyncSession, redis: Redis, user_id: int, username: str, item_kind: str, item_code: str,
                        amount: int, price_res: str, price: int) -> tuple[int, int]:
    """Предложить обмен игроку по юзернейму. → (id предложения, id получателя)."""
    _check_offer(item_kind, item_code, amount, price_res, price)
    target = await find_by_username(session, username.lstrip("@"))
    if target is None or target.city_id is None:
        raise ExchangeError("no_player")
    if target.id == user_id:
        raise ExchangeError("own")
    key = await _lock(redis, user_id)
    try:
        if await _count(session, ExchangeTrade, ExchangeTrade.from_id, user_id) >= EXCHANGE_MAX_TRADES:
            raise ExchangeError("too_many_trades", EXCHANGE_MAX_TRADES)
        if not await take_item(session, user_id, item_kind, item_code, amount):
            raise ExchangeError("not_enough")
        trade = ExchangeTrade(
            from_id=user_id, to_id=target.id, item_kind=item_kind, item_code=item_code, amount=amount,
            price_res=price_res, price=price, expires_at=_now() + timedelta(hours=EXCHANGE_TRADE_HOURS),
        )
        session.add(trade)
        await session.flush()
        result = (trade.id, target.id)
        await session.commit()
        return result
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


async def list_trades(session: AsyncSession, user_id: int) -> tuple[list[ExchangeTrade], list[ExchangeTrade]]:
    """(входящие, исходящие) действующие предложения."""
    now = _now()
    incoming = (await session.scalars(select(ExchangeTrade).where(ExchangeTrade.to_id == user_id, ExchangeTrade.expires_at > now))).all()
    outgoing = (await session.scalars(select(ExchangeTrade).where(ExchangeTrade.from_id == user_id, ExchangeTrade.expires_at > now))).all()
    return list(incoming), list(outgoing)


async def accept_trade(session: AsyncSession, redis: Redis, user_id: int, trade_id: int) -> Deal:
    key = await _lock(redis, user_id)
    try:
        trade = await session.scalar(
            select(ExchangeTrade).where(ExchangeTrade.id == trade_id, ExchangeTrade.to_id == user_id).with_for_update()
        )
        if trade is None or trade.expires_at <= _now():
            raise ExchangeError("gone")
        if not await spend(session, user_id, trade.price_res, trade.price):
            raise ExchangeError("no_money", trade.price)
        await grant(session, trade.from_id, trade.price_res, trade.price)
        await give_item(session, user_id, trade.item_kind, trade.item_code, trade.amount)
        deal = Deal("trade", trade.item_kind, trade.item_code, trade.amount, trade.price_res, trade.price, trade.from_id, user_id)
        await session.execute(delete(ExchangeTrade).where(ExchangeTrade.id == trade.id))
        await quest_event(session, user_id, TASK_EXCHANGE_DEAL)
        await session.commit()
        return deal
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


async def decline_trade(session: AsyncSession, redis: Redis, user_id: int, trade_id: int) -> Deal:
    """Отказ получателя или отзыв автором — предмет возвращается автору."""
    key = await _lock(redis, user_id)
    try:
        trade = await session.scalar(
            select(ExchangeTrade)
            .where(ExchangeTrade.id == trade_id, (ExchangeTrade.to_id == user_id) | (ExchangeTrade.from_id == user_id))
            .with_for_update()
        )
        if trade is None:
            raise ExchangeError("gone")
        await give_item(session, trade.from_id, trade.item_kind, trade.item_code, trade.amount)
        deal = Deal("trade_declined", trade.item_kind, trade.item_code, trade.amount, trade.price_res, trade.price, trade.from_id, trade.to_id)
        await session.execute(delete(ExchangeTrade).where(ExchangeTrade.id == trade.id))
        await session.commit()
        return deal
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


async def expire_trades(session_factory: async_sessionmaker[AsyncSession]) -> list[Deal]:
    """Фоновый проход: истёкшие предложения — предмет назад автору."""
    async with session_factory() as session:
        due = list((await session.scalars(select(ExchangeTrade.id).where(ExchangeTrade.expires_at <= _now()))).all())
    deals = []
    for trade_id in due:
        async with session_factory() as session:
            t = await session.scalar(select(ExchangeTrade).where(ExchangeTrade.id == trade_id).with_for_update())
            if t is None:
                continue
            await give_item(session, t.from_id, t.item_kind, t.item_code, t.amount)
            deals.append(Deal("trade_expired", t.item_kind, t.item_code, t.amount, t.price_res, t.price, t.from_id, t.to_id))
            await session.execute(delete(ExchangeTrade).where(ExchangeTrade.id == t.id))
            await session.commit()
    return deals


async def mine(session: AsyncSession, user_id: int) -> tuple[list[ExchangeLot], list[ExchangeAuction]]:
    lots = (await session.scalars(select(ExchangeLot).where(ExchangeLot.seller_id == user_id).order_by(ExchangeLot.created_at))).all()
    auctions = (await session.scalars(select(ExchangeAuction).where(ExchangeAuction.seller_id == user_id).order_by(ExchangeAuction.ends_at))).all()
    return list(lots), list(auctions)

