"""Зелья — магазин, действие, авто-зелья гения медицины (сервис). Дизайн — `config/potion`.

Эффект действующего зелья — временный источник бафов в Build (`services/build._potion_mods`),
зелье богатства — по пересечению окон ленивого дохода (`services/business`). Купить = сразу
выпить: один эффект на вид, новый тир заменяет прежний и запускает срок заново.
"""
from __future__ import annotations

from bot.constant.dev_quest import TASK_POTION

from bot.services.dev_quest import emit as quest_event

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.cache.keys import action_lock
from bot.config.game import ACTION_LOCK_MS
from bot.config.potion import (
    POTION_BASE_MAX_TIER,
    POTION_DISCOUNT_CAP,
    POTION_EFFECTS,
    POTION_PRICES,
    POTION_TIERS,
)
from bot.constant.potion import LOCK_ACTION_POTION, POTION_WEALTH, POTIONS
from bot.db.repositories import business as business_repo
from bot.db.repositories import potion as potion_repo
from bot.services.build import EconomyMods, capped, get_build


class UnknownPotionError(Exception):
    pass


class TierLockedError(Exception):
    def __init__(self, max_tier: int) -> None:
        super().__init__(max_tier)
        self.max_tier = max_tier


class NotEnoughCoinsError(Exception):
    def __init__(self, cost: int) -> None:
        super().__init__(cost)
        self.cost = cost


class AutoSlotsFullError(Exception):
    def __init__(self, slots: int) -> None:
        super().__init__(slots)
        self.slots = slots


class PotionBusyError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Offer:
    kind: str
    tier: int
    price: int
    minutes: int
    spec: dict
    unlocked: bool


@dataclass(frozen=True, slots=True)
class PotionState:
    kind: str
    tier: int  # действующий тир (0 — не действует)
    left_seconds: int
    auto_tier: int


@dataclass(frozen=True, slots=True)
class Catalog:
    max_tier: int
    discount: float
    duration: float
    power: float
    auto_slots: int
    states: dict[str, PotionState]


def _max_tier(eco: EconomyMods) -> int:
    return min(POTION_TIERS, max(POTION_BASE_MAX_TIER, eco.potion_tier))


def _price(tier: int, eco: EconomyMods) -> int:
    return max(1, int(POTION_PRICES[tier - 1] * (1 - capped(eco.potion_discount, POTION_DISCOUNT_CAP))))


def _minutes(kind: str, eco: EconomyMods) -> int:
    return round(POTION_EFFECTS[kind][0] * (1 + eco.potion_duration))


def _check(kind: str, tier: int) -> None:
    if kind not in POTIONS or not 1 <= tier <= POTION_TIERS:
        raise UnknownPotionError(f"{kind}:{tier}")


async def catalog(session: AsyncSession, user_id: int) -> Catalog:
    eco = (await get_build(session, user_id)).eco
    now = datetime.now(timezone.utc)
    states = {}
    for row in await potion_repo.list_for_user(session, user_id):
        left = max(0, int((row.expires_at - now).total_seconds())) if row.tier else 0
        states[row.kind] = PotionState(row.kind, row.tier if left else 0, left, row.auto_tier)
    return Catalog(
        max_tier=_max_tier(eco),
        discount=capped(eco.potion_discount, POTION_DISCOUNT_CAP),
        duration=eco.potion_duration,
        power=eco.potion_power,
        auto_slots=eco.potion_auto,
        states=states,
    )


async def offers(session: AsyncSession, user_id: int, kind: str) -> list[Offer]:
    if kind not in POTIONS:
        raise UnknownPotionError(kind)
    eco = (await get_build(session, user_id)).eco
    top = _max_tier(eco)
    return [
        Offer(kind, tier, _price(tier, eco), _minutes(kind, eco), POTION_EFFECTS[kind][1][tier - 1], tier <= top)
        for tier in range(1, POTION_TIERS + 1)
    ]


async def _drink(session: AsyncSession, user_id: int, kind: str, tier: int, eco: EconomyMods) -> Offer:
    """Списать NHCoin и выпить (без лока и без commit — шаг покупки и авто-продления)."""
    top = _max_tier(eco)
    if tier > top:
        raise TierLockedError(top)
    if kind == POTION_WEALTH:
        # Доход до сих пор — по старому окну зелья: зачислить его ДО смены окна.
        from bot.services.business import accrue

        await accrue(session, user_id)
    price, minutes = _price(tier, eco), _minutes(kind, eco)
    if not await business_repo.spend_coins(session, user_id, price):
        raise NotEnoughCoinsError(price)
    now = datetime.now(timezone.utc)
    await potion_repo.drink(session, user_id, kind, tier, now, now + timedelta(minutes=minutes))
    return Offer(kind, tier, price, minutes, POTION_EFFECTS[kind][1][tier - 1], True)


async def buy(session: AsyncSession, redis: Redis, user_id: int, kind: str, tier: int) -> Offer:
    """Купить и выпить: лок на клик (правило 2) + атомарное списание (правило 1). Коммитит."""
    _check(kind, tier)
    key = action_lock(user_id, LOCK_ACTION_POTION)
    if not await redis.set(key, "1", nx=True, px=ACTION_LOCK_MS):
        raise PotionBusyError
    try:
        offer = await _drink(session, user_id, kind, tier, (await get_build(session, user_id)).eco)
        await quest_event(session, user_id, TASK_POTION)
        await session.commit()
        return offer
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


async def set_auto(session: AsyncSession, user_id: int, kind: str, tier: int) -> None:
    """Авто-зелье: продлевать `kind` тиром `tier` (0 — выключить). Слоты — гений медицины."""
    if tier:
        _check(kind, tier)
        eco = (await get_build(session, user_id)).eco
        if tier > _max_tier(eco):
            raise TierLockedError(_max_tier(eco))
        if await potion_repo.count_auto(session, user_id, kind) >= eco.potion_auto:
            raise AutoSlotsFullError(eco.potion_auto)
    elif kind not in POTIONS:
        raise UnknownPotionError(kind)
    await potion_repo.set_auto(session, user_id, kind, tier)
    await session.commit()


async def renew_auto(session_factory: async_sessionmaker[AsyncSession]) -> list[tuple[int, str, int, str]]:
    """Фоновый проход: продлить авто-зелья, которые кончились или кончатся в ближайшую минуту.
    Каждое продление — своя транзакция (сбой одного не откатывает других). Если гений медицины
    больше не даёт слота/тира или не хватает NHCoin — авто-зелье выключается.
    → (игрок, вид, тир, итог: "ok" | "coins" | "locked")."""
    horizon = datetime.now(timezone.utc) + timedelta(seconds=60)
    async with session_factory() as session:
        due = await potion_repo.due_auto(session, horizon)
    done = []
    for user_id, kind, tier in due:
        async with session_factory() as session:
            eco = (await get_build(session, user_id)).eco
            outcome = "ok"
            try:
                if eco.potion_auto <= 0:
                    raise TierLockedError(_max_tier(eco))
                await _drink(session, user_id, kind, tier, eco)
            except TierLockedError:
                await session.rollback()
                outcome = "locked"
            except NotEnoughCoinsError:
                await session.rollback()
                outcome = "coins"
            if outcome != "ok":
                await potion_repo.disable_auto(session, user_id, kind)
            await session.commit()
            done.append((user_id, kind, tier, outcome))
    return done
