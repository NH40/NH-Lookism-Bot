"""Казино — общее: ставка (ресурс или отряд статистов) и детектор стратегии x3 из 1.0."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.cache.keys import casino_bets
from bot.config.casino import CASINO_HISTORY_TTL_SECONDS, CASINO_X3_RATIO_MAX, CASINO_X3_RATIO_MIN
from bot.constant.casino import STAKE_RESOURCE, STAKE_STATIST
from bot.constant.resource import NO_MINT_RESOURCES, RESOURCES
from bot.services.resource import StatistKey, give_statists, grant, spend, take_statists


class InvalidStakeError(Exception):
    pass


class NotEnoughError(Exception):
    pass


class X3StrategyError(Exception):
    """Третья подряд ставка ×3 от прошлой — казино просит остановиться (1.0)."""


class CasinoBusyError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Stake:
    kind: str  # STAKE_RESOURCE | STAKE_STATIST
    code: str  # код ресурса или `StatistKey.encode()`
    amount: int

    def validate(self) -> None:
        if self.amount <= 0:
            raise InvalidStakeError
        if self.kind == STAKE_RESOURCE and (self.code not in RESOURCES or self.code in NO_MINT_RESOURCES):
            raise InvalidStakeError
        if self.kind == STAKE_STATIST:
            try:
                StatistKey.decode(self.code)
            except ValueError as exc:
                raise InvalidStakeError from exc
        if self.kind not in (STAKE_RESOURCE, STAKE_STATIST):
            raise InvalidStakeError

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def of(cls, data: dict) -> "Stake":
        return cls(data["kind"], data["code"], int(data["amount"]))


async def take_stake(session: AsyncSession, user_id: int, stake: Stake) -> None:
    """Списать ставку (НЕ коммитит). NotEnoughError — не хватает."""
    stake.validate()
    if stake.kind == STAKE_RESOURCE:
        ok = await spend(session, user_id, stake.code, stake.amount)
    else:
        ok = await take_statists(session, user_id, StatistKey.decode(stake.code), stake.amount)
    if not ok:
        raise NotEnoughError


async def pay_stake(session: AsyncSession, user_id: int, stake: Stake, amount: int) -> None:
    """Выплатить `amount` в валюте ставки (НЕ коммитит)."""
    if amount <= 0:
        return
    if stake.kind == STAKE_RESOURCE:
        await grant(session, user_id, stake.code, amount)
    else:
        await give_statists(session, user_id, StatistKey.decode(stake.code), amount)


async def check_x3(redis: Redis, user_id: int, game: str, stake: Stake) -> None:
    """Детектор x3 (1.0): если эта ставка — третья подряд, растущая ≈ втрое, — отказ. Иначе
    ставка запоминается (последние 3, TTL час)."""
    key = casino_bets(user_id, game, f"{stake.kind}:{stake.code}")
    history = [int(v) for v in await redis.lrange(key, 0, -1)] + [stake.amount]

    def tripled(a: int, b: int) -> bool:
        return a > 0 and CASINO_X3_RATIO_MIN <= b / a <= CASINO_X3_RATIO_MAX

    if len(history) >= 3 and tripled(history[-3], history[-2]) and tripled(history[-2], history[-1]):
        raise X3StrategyError
    await redis.rpush(key, str(stake.amount))
    await redis.ltrim(key, -3, -1)
    await redis.expire(key, CASINO_HISTORY_TTL_SECONDS)
