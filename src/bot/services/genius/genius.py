"""Гениальность (сервис). Дизайн — `docs/design/development_systems.md`, «Гениальность».

Пользователь 2026-10-02:
- первая гениальность выпадает **случайно при регистрации** и остаётся навсегда
  (`ensure_genius` — при `/start` и входе в «Развитие»; игроки, зарегистрированные раньше,
  получают её при первом таком заходе);
- **активна одна**, свапается (не чаще раза в `GENIUS_SWAP_COOLDOWN_SECONDS`);
- качается **фрагментами гениальности** с босса Элиты;
- новые — **прокрутом в магазине** за фрагменты + NHCoin; выпала имеющаяся — крутка
  потеряна.

Бафы активной гениальности собирает `services/build` — здесь только владение и уровни.
Родословная Джинена удешевляет уровни **гения медицины** (`medicine_discount`).
"""
from __future__ import annotations

from bot.constant.dev_quest import TASK_DEV_LEVEL

from bot.services.dev_quest import emit as quest_event

import random
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.cache.keys import action_lock, swap_cooldown
from bot.config.development import MAX_LEVEL
from bot.config.game import ACTION_LOCK_MS
from bot.config.genius import (
    GENIUS_ROLL_COINS,
    GENIUS_ROLL_FRAGMENTS,
    GENIUS_SWAP_COOLDOWN_SECONDS,
    genius_level_cost,
)
from bot.constant.genius import GENIUS_MEDICINE, GENIUSES, LOCK_ACTION_GENIUS
from bot.db.repositories import genius as genius_repo
from bot.constant.activity import ACT_DEVELOPMENT
from bot.services.activity import log as log_activity
from bot.texts.activity import LOG_GENIUS_LEVEL, LOG_GENIUS_NEW
from bot.texts.genius import GENIUS_NAMES
from bot.services.build import capped, get_build


class UnknownGeniusError(Exception):
    pass


class GeniusNotOwnedError(Exception):
    pass


class GeniusMaxLevelError(Exception):
    pass


class NotEnoughFragmentsError(Exception):
    def __init__(self, cost: int, have: int, coins: int = 0) -> None:
        super().__init__(cost, have)
        self.cost, self.have, self.coins = cost, have, coins


class SwapOnCooldownError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(retry_after_seconds)
        self.retry_after_seconds = retry_after_seconds


class GeniusBusyError(Exception):
    """Предыдущее действие с гениальностью ещё обрабатывается (двойной клик)."""


@dataclass(frozen=True, slots=True)
class GeniusView:
    active: str | None
    owned: dict[str, int]  # код → уровень
    fragments: int
    coins: int
    swap_cooldown: int
    next_costs: dict[str, int | None]  # цена следующего уровня, None — максимум


@dataclass(frozen=True, slots=True)
class RollResult:
    code: str
    duplicate: bool  # выпала уже имеющаяся — крутка потеряна



async def _swap_cd(session: AsyncSession, user_id: int, seconds: int) -> int:
    """КД переключения с мастерством Скорости («−10/20/30% ко ВСЕМ КД», raw-notes; до 2026-10-12
    переключения его не учитывали)."""
    from bot.services.characteristic import get_combat_profile

    return (await get_combat_profile(session, user_id)).cooldown(seconds)

async def ensure_genius(session: AsyncSession, user_id: int, rng: random.Random | None = None) -> str | None:
    """Первая гениальность — случайно, если у игрока ещё нет ни одной. Коммитит, если выдала.
    → код выданной (None — уже была)."""
    if await genius_repo.list_owned(session, user_id):
        return None
    code = (rng or random).choice(GENIUSES)
    if await genius_repo.add(session, user_id, code):
        await genius_repo.set_active_if_missing(session, user_id, code)
        await session.commit()
        return code
    return None


async def _level_cost(session: AsyncSession, user_id: int, code: str, next_level: int) -> int:
    cost = genius_level_cost(next_level)
    if code == GENIUS_MEDICINE:
        discount = (await get_build(session, user_id)).eco.medicine_discount
        cost = max(1, round(cost * (1 - capped(discount, 0.6))))
    return cost


async def get_view(session: AsyncSession, redis: Redis, user_id: int) -> GeniusView:
    owned = dict(await genius_repo.list_owned(session, user_id))
    active, fragments, coins = await genius_repo.get_state(session, user_id)
    costs = {
        code: (await _level_cost(session, user_id, code, level + 1) if level < MAX_LEVEL else None)
        for code, level in owned.items()
    }
    return GeniusView(
        active=active, owned=owned, fragments=fragments, coins=coins,
        swap_cooldown=max(0, await redis.ttl(swap_cooldown(user_id, "genius"))),
        next_costs=costs,
    )


async def activate(session: AsyncSession, redis: Redis, user_id: int, code: str) -> None:
    if code not in GENIUSES:
        raise UnknownGeniusError(code)
    owned = dict(await genius_repo.list_owned(session, user_id))
    if code not in owned:
        raise GeniusNotOwnedError
    key = swap_cooldown(user_id, "genius")
    if not await redis.set(key, "1", nx=True, ex=await _swap_cd(session, user_id, GENIUS_SWAP_COOLDOWN_SECONDS)):
        raise SwapOnCooldownError(max(0, await redis.ttl(key)))
    await genius_repo.set_active(session, user_id, code)
    await session.commit()


async def level_up(session: AsyncSession, user_id: int, code: str) -> int:
    """+1 уровень за фрагменты. Списание и рост уровня — одной транзакцией, оба шага
    условные (правило 1). → новый уровень."""
    owned = dict(await genius_repo.list_owned(session, user_id))
    if code not in owned:
        raise GeniusNotOwnedError
    current = owned[code]
    if current >= MAX_LEVEL:
        raise GeniusMaxLevelError
    cost = await _level_cost(session, user_id, code, current + 1)
    if not await genius_repo.spend_fragments(session, user_id, cost):
        _, have, _ = await genius_repo.get_state(session, user_id)
        raise NotEnoughFragmentsError(cost, have)
    if not await genius_repo.bump_level(session, user_id, code, current):
        await session.rollback()
        raise GeniusMaxLevelError
    await log_activity(session, user_id, ACT_DEVELOPMENT, LOG_GENIUS_LEVEL.format(name=GENIUS_NAMES[code], level=current + 1))
    await quest_event(session, user_id, TASK_DEV_LEVEL)
    await session.commit()
    return current + 1


async def roll(session: AsyncSession, redis: Redis, user_id: int, rng: random.Random | None = None) -> RollResult:
    """Прокрут новой гениальности в магазине. Redis-лок на клик (правило 2) + атомарное
    списание фрагментов и NHCoin одним UPDATE (правило 1)."""
    key = action_lock(user_id, LOCK_ACTION_GENIUS)
    if not await redis.set(key, "1", nx=True, px=ACTION_LOCK_MS):
        raise GeniusBusyError
    try:
        if not await genius_repo.spend_fragments(session, user_id, GENIUS_ROLL_FRAGMENTS, GENIUS_ROLL_COINS):
            _, have, coins = await genius_repo.get_state(session, user_id)
            raise NotEnoughFragmentsError(GENIUS_ROLL_FRAGMENTS, have, coins)
        code = (rng or random).choice(GENIUSES)
        duplicate = not await genius_repo.add(session, user_id, code)
        if not duplicate:
            await log_activity(session, user_id, ACT_DEVELOPMENT, LOG_GENIUS_NEW.format(name=GENIUS_NAMES[code]))
        await session.commit()
        return RollResult(code=code, duplicate=duplicate)
    finally:
        await redis.delete(key)
