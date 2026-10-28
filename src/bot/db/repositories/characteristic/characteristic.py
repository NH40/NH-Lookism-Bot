"""Характеристики игрока — ранги, потенциал, очки развития (репозиторий).

Функции записи НЕ коммитят: вложение очков и начисление за тренировку коммитит сервис.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.characteristic import (
    MASTERY_ENDURANCE,
    MASTERY_SPEED,
    MASTERY_STRENGTH,
    MASTERY_TECHNIQUE,
    STAT_AGILITY,
    STAT_ENDURANCE,
    STAT_SPEED,
    STAT_STRENGTH,
)
from bot.db.models.user import User

_STAT_COLUMNS = {
    STAT_STRENGTH: User.stat_strength,
    STAT_SPEED: User.stat_speed,
    STAT_ENDURANCE: User.stat_endurance,
    STAT_AGILITY: User.stat_agility,
}


@dataclass(frozen=True, slots=True)
class StatsRow:
    ranks: dict[str, int]  # код характеристики → индекс ранга
    potential: str | None
    dev_points: int


def _select():
    return select(*_STAT_COLUMNS.values(), User.potential, User.dev_points)


def _row(row) -> StatsRow:
    values = list(row)
    return StatsRow(ranks=dict(zip(_STAT_COLUMNS, values[:4])), potential=values[4], dev_points=values[5])


async def get_stats(session: AsyncSession, user_id: int, *, for_update: bool = False) -> StatsRow | None:
    stmt = _select().where(User.id == user_id)
    if for_update:
        stmt = stmt.with_for_update()
    row = (await session.execute(stmt)).one_or_none()
    return _row(row) if row is not None else None


async def get_strength(session: AsyncSession, user_id: int) -> int:
    return await session.scalar(select(User.stat_strength).where(User.id == user_id)) or 0


async def invest(session: AsyncSession, user_id: int, *, stat: str, current: int, ranks: int, cost: int) -> bool:
    """Поднимает характеристику на `ranks` и списывает `cost` ОДНИМ `UPDATE` с условием на
    текущий ранг и баланс (правило 1): двойной клик не купит ранги дважды по одной цене."""
    col = _STAT_COLUMNS[stat]
    result = await session.execute(
        update(User)
        .where(User.id == user_id, col == current, User.dev_points >= cost)
        .values({col: col + ranks, User.dev_points: User.dev_points - cost})
    )
    return result.rowcount > 0


async def add_points(session: AsyncSession, user_id: int, points: int) -> int:
    """Начисляет очки развития, возвращает новый баланс."""
    return await session.scalar(
        update(User).where(User.id == user_id).values(dev_points=User.dev_points + points).returning(User.dev_points)
    )


async def set_potential_if_missing(session: AsyncSession, user_id: int, potential: str) -> str:
    """Выдаёт потенциал, если его ещё нет (`WHERE potential IS NULL` — не перетрёт выданный),
    и возвращает актуальный. Нужен игрокам, зарегистрированным до появления потенциала."""
    await session.execute(update(User).where(User.id == user_id, User.potential.is_(None)).values(potential=potential))
    return await session.scalar(select(User.potential).where(User.id == user_id))


@dataclass(frozen=True, slots=True)
class CombatRow:
    ranks: dict[str, int]  # код характеристики → индекс ранга
    mastery: dict[str, int]  # код мастерства → ступень 0..3


_MASTERY_COLUMNS = {
    MASTERY_STRENGTH: User.mastery_strength,
    MASTERY_SPEED: User.mastery_speed,
    MASTERY_ENDURANCE: User.mastery_endurance,
    MASTERY_TECHNIQUE: User.mastery_technique,
}


async def get_combat_row(session: AsyncSession, user_id: int) -> CombatRow:
    """Характеристики и мастерство одним запросом — всё, что влияет на бой и КД игрока."""
    row = (
        await session.execute(select(*_STAT_COLUMNS.values(), *_MASTERY_COLUMNS.values()).where(User.id == user_id))
    ).one_or_none()
    if row is None:
        return CombatRow(ranks={k: 0 for k in _STAT_COLUMNS}, mastery={k: 0 for k in _MASTERY_COLUMNS})
    values = list(row)
    return CombatRow(ranks=dict(zip(_STAT_COLUMNS, values[:4])), mastery=dict(zip(_MASTERY_COLUMNS, values[4:])))



# --- очки потенциала (2026-10-28) ---

_AWARD_POTENTIAL_SQL = text(
    """
    UPDATE users
    SET potential_points = potential_points + CAST(:points AS bigint),
        potential_point_gates = potential_point_gates || jsonb_build_object(CAST(:source AS text), CAST(:now AS bigint))
    WHERE id = :uid
      AND COALESCE((potential_point_gates ->> CAST(:source AS text))::bigint, 0) <= CAST(:now AS bigint) - CAST(:gate AS bigint)
    RETURNING potential_points
    """
)


async def award_potential_points(session: AsyncSession, user_id: int, source: str, points: int, gate_seconds: int, now: int) -> int | None:
    """→ новый баланс; None — интервал источника ещё не прошёл. НЕ коммитит."""
    return await session.scalar(
        _AWARD_POTENTIAL_SQL, {"uid": user_id, "source": source, "points": points, "gate": gate_seconds, "now": now}
    )


async def upgrade_potential(session: AsyncSession, user_id: int, current: str, nxt: str, cost: int) -> bool:
    """Потенциал на ступень выше за очки — условный UPDATE (правило 1): двойной клик не спишет дважды."""
    result = await session.execute(text(
        "UPDATE users SET potential = :nxt, potential_points = potential_points - :cost "
        "WHERE id = :uid AND potential = :cur AND potential_points >= :cost"
    ), {"uid": user_id, "cur": current, "nxt": nxt, "cost": cost})
    return result.rowcount > 0
