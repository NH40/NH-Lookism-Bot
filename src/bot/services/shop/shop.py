"""Магазин — тикеты за NHCoin (сервис).

Счётчик «куплено сегодня» — в Redis (`shop:tk:{день}:{игрок}`, живёт до конца суток): атомарный
INCRBY резервирует место в дневном лимите до списания; если покупка сорвалась — место возвращается.
Сбой Redis в худшем случае обнулит счётчик дня — деньги и тикеты при этом остаются в БД верными.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.shop import SHOP_TICKET_PRICE, SHOP_TICKETS_DAILY_LIMIT
from bot.config.game import ACTION_LOCK_MS
from bot.constant.ledger import REASON_SHOP
from bot.constant.resource import RES_TICKETS
from bot.constant.shop import LOCK_ACTION_SHOP
from bot.db.repositories import business as business_repo
from bot.cache.keys import action_lock
from bot.utils.log_context import coin_reason


class ShopBusyError(Exception):
    pass


class TicketsDailyLimitError(Exception):
    def __init__(self, left: int) -> None:
        super().__init__(left)
        self.left = left


class TicketsNotEnoughCoinsError(Exception):
    def __init__(self, cost: int) -> None:
        super().__init__(cost)
        self.cost = cost


@dataclass(frozen=True, slots=True)
class TicketsOffer:
    price: int
    limit: int
    bought: int

    @property
    def left(self) -> int:
        return max(0, self.limit - self.bought)


def _key(user_id: int) -> str:
    from bot.services.quest import today

    return f"shop:tk:{today().isoformat()}:{user_id}"


def _day_end_ts() -> int:
    from bot.config.quest import QUEST_DAY_TZ

    now = datetime.now(QUEST_DAY_TZ)
    return int(datetime.combine(now.date() + timedelta(days=1), time.min, QUEST_DAY_TZ).timestamp()) + 3600


async def tickets_offer(redis: Redis, user_id: int) -> TicketsOffer:
    bought = int(await redis.get(_key(user_id)) or 0)
    return TicketsOffer(price=SHOP_TICKET_PRICE, limit=SHOP_TICKETS_DAILY_LIMIT, bought=bought)


async def buy_tickets(session: AsyncSession, redis: Redis, user_id: int, amount: int) -> int:
    """Купить `amount` тикетов. → цена. Лок на клик (правило 2), атомарное списание (правило 1). Коммитит."""
    from bot.services.business import accrue
    from bot.services.resource import grant

    if amount < 1:
        raise TicketsDailyLimitError((await tickets_offer(redis, user_id)).left)
    lock = action_lock(user_id, LOCK_ACTION_SHOP)
    if not await redis.set(lock, "1", nx=True, px=ACTION_LOCK_MS):
        raise ShopBusyError
    key = _key(user_id)
    reserved = False
    try:
        total = await redis.incrby(key, amount)
        reserved = True
        await redis.expireat(key, _day_end_ts())
        if total > SHOP_TICKETS_DAILY_LIMIT:
            raise TicketsDailyLimitError(max(0, SHOP_TICKETS_DAILY_LIMIT - (total - amount)))
        cost = amount * SHOP_TICKET_PRICE
        await accrue(session, user_id)
        with coin_reason(REASON_SHOP):
            if not await business_repo.spend_coins(session, user_id, cost):
                raise TicketsNotEnoughCoinsError(cost)
        await grant(session, user_id, RES_TICKETS, amount)
        await session.commit()
        reserved = False
        return cost
    except Exception:
        await session.rollback()
        raise
    finally:
        if reserved:
            await redis.decrby(key, amount)
        await redis.delete(lock)
