"""Вклады (сервис). Дизайн — `config/deposit`.

Вклад — ресурс на срок под процент: тело списывается сразу (на балансе его нет — саботажу и
войне не достать), по сроку забирается с процентами; досрочно — только тело, без процентов.
Сгорают вклады вместе с прогрессом (пробуждение, удаление банды) — иначе через них
проносили бы NHCoin мимо сброса. Лок на клик (правило 2) + атомарные списания (правило 1)
+ строка вклада `FOR UPDATE` при выемке (двойной клик не выплатит дважды).
"""
from __future__ import annotations

from bot.services.build import get_build
from bot.constant.dev_quest import TASK_DEPOSIT

from bot.services.dev_quest import emit as quest_event

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.cache.keys import action_lock
from bot.config.deposit import (
    DEPOSIT_CAPS,
    DEPOSIT_COINS_MIN_CAP,
    DEPOSIT_MAX_ACTIVE,
    DEPOSIT_OTHER_RATE_SHARE,
    DEPOSIT_RATES,
)
from bot.config.game import ACTION_LOCK_MS
from bot.constant.deposit import LOCK_ACTION_DEPOSIT
from bot.constant.resource import NO_MINT_RESOURCES, RES_COINS, RESOURCES
from bot.db.models.deposit import Deposit
from bot.services.business import get_wallet
from bot.services.resource import grant, spend


class DepositBusyError(Exception):
    pass


class InvalidTermError(Exception):
    pass


class InvalidAmountError(Exception):
    def __init__(self, cap: int) -> None:
        super().__init__(cap)
        self.cap = cap


class TooManyDepositsError(Exception):
    pass


class NotEnoughError(Exception):
    pass


class DepositNotFoundError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class DepositView:
    id: int
    resource: str
    amount: int
    rate: float
    hours: int
    left_seconds: int

    @property
    def ready(self) -> bool:
        return self.left_seconds <= 0

    @property
    def payout(self) -> int:
        return int(self.amount * (1 + self.rate))


def rate_for(resource: str, hours: int) -> float:
    if hours not in DEPOSIT_RATES or resource not in RESOURCES or resource in NO_MINT_RESOURCES:
        raise InvalidTermError(hours)
    rate = DEPOSIT_RATES[hours]
    return rate if resource == RES_COINS else rate * DEPOSIT_OTHER_RATE_SHARE


async def cap_for(session: AsyncSession, user_id: int, resource: str) -> int:
    """Потолок одного вклада: NHCoin — суточный доход бизнеса (не меньше минимума), остальное —
    фиксированные потолки."""
    if resource == RES_COINS:
        wallet = await get_wallet(session, user_id)
        daily = int(wallet.per_minute * 60 * 24) if wallet else 0
        return max(DEPOSIT_COINS_MIN_CAP, daily)
    return DEPOSIT_CAPS.get(resource, 0)


async def list_deposits(session: AsyncSession, user_id: int) -> list[DepositView]:
    now = datetime.now(timezone.utc)
    rows = (await session.scalars(select(Deposit).where(Deposit.user_id == user_id).order_by(Deposit.matures_at))).all()
    return [
        DepositView(d.id, d.resource, d.amount, d.rate, d.hours, max(0, int((d.matures_at - now).total_seconds())))
        for d in rows
    ]


async def _lock(redis: Redis, user_id: int) -> str:
    key = action_lock(user_id, LOCK_ACTION_DEPOSIT)
    if not await redis.set(key, "1", nx=True, px=ACTION_LOCK_MS):
        raise DepositBusyError
    return key


async def open_deposit(session: AsyncSession, redis: Redis, user_id: int, resource: str, hours: int, amount: int) -> DepositView:
    rate = rate_for(resource, hours)
    positions = (await get_build(session, user_id)).positions
    if positions is not None:  # «Инвестор» (Бизнесмен): проценты вклада выше
        rate *= 1 + positions.get("deposit_rate")
    cap = await cap_for(session, user_id, resource)
    if not 0 < amount <= cap:
        raise InvalidAmountError(cap)
    key = await _lock(redis, user_id)
    try:
        active = await session.scalar(select(func.count()).where(Deposit.user_id == user_id))
        if active >= DEPOSIT_MAX_ACTIVE:
            raise TooManyDepositsError
        if not await spend(session, user_id, resource, amount):
            raise NotEnoughError
        deposit = Deposit(
            user_id=user_id, resource=resource, amount=amount, rate=rate, hours=hours,
            matures_at=datetime.now(timezone.utc) + timedelta(hours=hours),
        )
        session.add(deposit)
        await session.flush()
        view = DepositView(deposit.id, resource, amount, rate, hours, hours * 3600)
        await quest_event(session, user_id, TASK_DEPOSIT)
        await session.commit()
        return view
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)


async def claim(session: AsyncSession, redis: Redis, user_id: int, deposit_id: int) -> tuple[int, bool]:
    """Забрать вклад: созрел — с процентами, нет — только тело. → (выдано, с процентами ли)."""
    key = await _lock(redis, user_id)
    try:
        deposit = await session.scalar(
            select(Deposit).where(Deposit.id == deposit_id, Deposit.user_id == user_id).with_for_update()
        )
        if deposit is None:
            raise DepositNotFoundError
        matured = deposit.matures_at <= datetime.now(timezone.utc)
        payout = int(deposit.amount * (1 + deposit.rate)) if matured else deposit.amount
        await session.execute(delete(Deposit).where(Deposit.id == deposit.id))
        await grant(session, user_id, deposit.resource, payout)
        await session.commit()
        return payout, matured
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(key)
