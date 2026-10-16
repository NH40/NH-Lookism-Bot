"""Контракты статистов — наём на срок в магазине (сервис).

Пользователь 2026-10-04: игрок сам выбирает ранг — не выше потолка вербовки по его влиянию
(тот же потолок, что у вербовки, с бонусом рангов систем развития), вводит количество, видит
цену и нанимает бойцов на 24 часа. Наёмники встают в лагерь атаки
(`services/district/army.load_camp`), воюют и гибнут как свои («если умрут — его проблема»),
не тренируются и уходят по истечении срока. Родословная Джинчоля: дешевле
(`contract_discount`) и дольше (`contract_duration`).
"""
from __future__ import annotations

from bot.constant.dev_quest import TASK_CONTRACT

from bot.services.dev_quest import emit as quest_event

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.cache.keys import action_lock
from bot.config.characteristic import extra_power_for_rank
from bot.config.contract import (
    CONTRACT_COINS_PER_POWER,
    CONTRACT_DISCOUNT_CAP,
    CONTRACT_HOURS,
    CONTRACT_MAX_QUANTITY,
)
from bot.config.game import ACTION_LOCK_MS
from bot.constant.characteristic import RANK_INDEX, RANK_LADDER
from bot.constant.shop import LOCK_ACTION_SHOP
from bot.db.repositories import business as business_repo
from bot.db.repositories import contract as contract_repo
from bot.db.repositories.phase import get_phase
from bot.services.build import capped, get_build
from bot.services.district import get_influence
from bot.services.recruit.recruit import PHASE_RANK_CAP_INDEX


class RankNotAvailableError(Exception):
    """Ранг выше потолка влияния (или такого ранга нет)."""


class InvalidQuantityError(Exception):
    pass


class NotEnoughCoinsError(Exception):
    def __init__(self, cost: int) -> None:
        super().__init__(cost)
        self.cost = cost


class ShopBusyError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Terms:
    """Условия найма для игрока: потолок ранга, цена бойца каждого ранга, срок."""

    ceiling: str
    discount: float
    hours: float

    def unit_price(self, rank: str) -> int:
        return max(1, int(extra_power_for_rank(rank) * CONTRACT_COINS_PER_POWER * (1 - self.discount)))

    @property
    def ranks(self) -> list[str]:
        """Доступные ранги — от потолка вниз."""
        return list(reversed(RANK_LADDER[: RANK_INDEX[self.ceiling] + 1]))


@dataclass(frozen=True, slots=True)
class Quote:
    rank: str
    quantity: int
    unit_price: int
    total: int
    hours: float
    power: int  # мощь одного бойца


@dataclass(frozen=True, slots=True)
class ActiveContract:
    rank: str
    quantity: int
    expires_in_seconds: int


async def terms(session: AsyncSession, user_id: int) -> Terms:
    phase = (await get_phase(session, user_id))[0]
    eco = (await get_build(session, user_id)).eco
    bonus = eco.recruit_rank_bonus
    ceiling = min(PHASE_RANK_CAP_INDEX[phase] + bonus, await get_influence(session, user_id) + bonus, len(RANK_LADDER) - 1)
    return Terms(
        ceiling=RANK_LADDER[max(0, ceiling)],
        discount=capped(eco.contract_discount, CONTRACT_DISCOUNT_CAP),
        hours=CONTRACT_HOURS * (1 + eco.contract_duration),
    )


async def quote(session: AsyncSession, user_id: int, rank: str, quantity: int) -> Quote:
    """Сколько стоит нанять `quantity` бойцов ранга `rank` — с проверкой потолка влияния."""
    if not 0 < quantity <= CONTRACT_MAX_QUANTITY:
        raise InvalidQuantityError(quantity)
    current = await terms(session, user_id)
    if rank not in RANK_INDEX or RANK_INDEX[rank] > RANK_INDEX[current.ceiling]:
        raise RankNotAvailableError(rank)
    unit = current.unit_price(rank)
    return Quote(rank, quantity, unit, unit * quantity, current.hours, extra_power_for_rank(rank))


async def active(session: AsyncSession, user_id: int) -> list[ActiveContract]:
    now = datetime.now(timezone.utc)
    return [
        ActiveContract(c.rank, c.quantity, max(0, int((c.expires_at - now).total_seconds())))
        for c in await contract_repo.list_active(session, user_id)
    ]


async def buy(session: AsyncSession, redis: Redis, user_id: int, rank: str, quantity: int) -> Quote:
    """Нанять: условия пересчитываются заново (влияние могло упасть с экрана цены), Redis-лок
    на клик (правило 2) + атомарное списание NHCoin (правило 1) + контракт — один commit."""
    offer = await quote(session, user_id, rank, quantity)
    key = action_lock(user_id, LOCK_ACTION_SHOP)
    if not await redis.set(key, "1", nx=True, px=ACTION_LOCK_MS):
        raise ShopBusyError
    try:
        if not await business_repo.spend_coins(session, user_id, offer.total):
            raise NotEnoughCoinsError(offer.total)
        expires = datetime.now(timezone.utc) + timedelta(hours=offer.hours)
        await contract_repo.create(session, user_id, offer.rank, offer.quantity, expires)
        await quest_event(session, user_id, TASK_CONTRACT)
        await session.commit()
        return offer
    finally:
        await redis.delete(key)


async def purge(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        await contract_repo.purge(session)
        await session.commit()
