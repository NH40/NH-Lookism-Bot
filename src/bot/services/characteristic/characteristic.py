"""Характеристики игрока — Сила, Скорость, Выносливость, Ловкость, Потенциал (сервис).

raw-notes «Профиль» + ответы пользователя 2026-09-30:
- все характеристики стартуют с F- (кроме Потенциала);
- ранг покупается за очки развития: шаг n→n+1 стоит 1 + n//2 (702 очка до Infinity);
- очки — из личной тренировки (`services/training.train_personal`), их число зависит от
  Потенциала;
- Потенциал — 8 стадий, случайно при регистрации, не прокачивается; новый случайный —
  только при перерождении кулака (механика позже);
- Сила: +1% к мощи за ранг (`strength_power_multiplier` — в бою и в сводке армии).
  Скорость/Выносливость/Ловкость в бою — ждут чисел от пользователя (docs/ROADMAP.md, 1.6).
"""
from __future__ import annotations

from bot.constant.dev_quest import TASK_STAT_INVEST

from bot.services.dev_quest import emit as quest_event

import random
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.build import capped, get_build

from bot.config.characteristic import (
    POTENTIAL_START_PERCENT,
    STAT_MAX_INDEX,
    stat_rank_up_cost,
    stat_ranks_affordable,
    strength_power_percent,
)
from bot.constant.characteristic import RANK_LADDER, STAT_STRENGTH, STATS, STATS_UP_FIVE, STATS_UP_MAX, STATS_UP_ONE
from bot.db.repositories import characteristic as char_repo
from bot.services.characteristic.combat import get_combat_profile


class UnknownStatError(Exception):
    pass


class StatMaxedError(Exception):
    pass


class NotEnoughPointsError(Exception):
    def __init__(self, cost: int, points: int) -> None:
        self.cost = cost
        self.points = points


def roll_potential(rng: random.Random | None = None) -> str:
    """Стадия потенциала при регистрации — по весам `POTENTIAL_START_PERCENT`."""
    rng = rng or random
    stages = list(POTENTIAL_START_PERCENT)
    return rng.choices(stages, weights=[POTENTIAL_START_PERCENT[s] for s in stages])[0]


async def ensure_potential(session: AsyncSession, user_id: int) -> str:
    """Потенциал игрока; тем, у кого его ещё нет (страховка — миграция выдала всем), выдаёт
    случайный один раз и коммитит сразу: иначе на экранах только для чтения он бы
    перевыпадал при каждом открытии."""
    row = await char_repo.get_stats(session, user_id)
    if row is not None and row.potential:
        return row.potential
    potential = await char_repo.set_potential_if_missing(session, user_id, roll_potential())
    await session.commit()
    return potential


async def _stat_discount(session: AsyncSession, user_id: int) -> float:
    """Скидка на ранги характеристик от систем развития (не больше половины цены)."""
    return capped((await get_build(session, user_id)).eco.stat_cost_discount, 0.5)


@dataclass(frozen=True, slots=True)
class StatView:
    code: str
    index: int
    rank: str
    next_cost: int | None  # None — уже Infinity


@dataclass(frozen=True, slots=True)
class StatsView:
    stats: list[StatView]
    potential: str
    dev_points: int
    strength_power_percent: int


async def get_stats_view(session: AsyncSession, user_id: int) -> StatsView:
    potential = await ensure_potential(session, user_id)
    row = await char_repo.get_stats(session, user_id)
    discount = await _stat_discount(session, user_id)
    stats = [
        StatView(
            code=code,
            index=row.ranks[code],
            rank=RANK_LADDER[row.ranks[code]],
            next_cost=stat_rank_up_cost(row.ranks[code], discount) if row.ranks[code] < STAT_MAX_INDEX else None,
        )
        for code in STATS
    ]
    return StatsView(
        stats=stats,
        potential=potential,
        dev_points=row.dev_points,
        strength_power_percent=strength_power_percent(RANK_LADDER[row.ranks[STAT_STRENGTH]]),
    )


@dataclass(frozen=True, slots=True)
class InvestResult:
    stat: str
    ranks: int
    cost: int
    new_rank: str


async def invest(session: AsyncSession, user_id: int, stat: str, mode: str) -> InvestResult:
    """Вкладывает очки: +1 ранг, +5 рангов (сколько хватит, не больше 5) или максимум, на что
    хватает очков. Строка игрока под `FOR UPDATE`, покупка — один условный UPDATE. Коммитит."""
    if stat not in STATS or mode not in (STATS_UP_ONE, STATS_UP_FIVE, STATS_UP_MAX):
        raise UnknownStatError
    row = await char_repo.get_stats(session, user_id, for_update=True)
    current = row.ranks[stat]
    if current >= STAT_MAX_INDEX:
        raise StatMaxedError
    limit = {STATS_UP_ONE: 1, STATS_UP_FIVE: 5, STATS_UP_MAX: None}[mode]
    discount = await _stat_discount(session, user_id)
    ranks, cost = stat_ranks_affordable(current, row.dev_points, limit, discount)
    if ranks == 0:
        raise NotEnoughPointsError(cost=stat_rank_up_cost(current, discount), points=row.dev_points)
    if not await char_repo.invest(session, user_id, stat=stat, current=current, ranks=ranks, cost=cost):
        raise NotEnoughPointsError(cost=cost, points=row.dev_points)
    await quest_event(session, user_id, TASK_STAT_INVEST, ranks)
    await session.commit()
    return InvestResult(stat=stat, ranks=ranks, cost=cost, new_rank=RANK_LADDER[current + ranks])


async def strength_power_multiplier(session: AsyncSession, user_id: int) -> int:
    """Множитель мощи армии игрока в процентах (100 = без бонуса): Сила +1% за ранг плюс
    мастерство Силы +10/25/50%."""
    return (await get_combat_profile(session, user_id)).power_percent
