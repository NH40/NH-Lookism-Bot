"""Война императоров — цели, вызовы, переход городов (репозиторий).

Функции записи НЕ коммитят — коммитит сервис одним разом (правило 10).
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.empire import WAR_PENDING, WAR_RESOLVED
from bot.constant.phase import PHASE_FIST
from bot.db.models.city import City
from bot.db.models.country import Country
from bot.db.models.emperor_tax import EmperorTaxOverride
from bot.db.models.emperor_war import EmperorWar
from bot.db.models.user import User


@dataclass(frozen=True, slots=True)
class EmperorRow:
    user_id: int
    username: str | None
    display_name: str | None
    country_name: str | None
    cities: int
    nh_coins: int


def _cities_count():
    return (
        select(func.count()).select_from(City).where(City.emperor_id == User.id).correlate(User).scalar_subquery()
    )


def _emperors_query(cities):
    return (
        select(User.id, User.username, User.display_name, Country.name, cities, User.nh_coins)
        .outerjoin(Country, Country.code == User.country_code)
        .where(User.phase == PHASE_FIST)
    )


async def list_emperors(
    session: AsyncSession, *, exclude_id: int, offset: int, limit: int
) -> tuple[list[EmperorRow], bool]:
    """Другие императоры — страница + флаг «есть ещё» (`LIMIT limit+1`, без COUNT)."""
    cities = _cities_count()
    rows = (
        await session.execute(
            _emperors_query(cities)
            .where(User.id != exclude_id)
            .order_by(cities.desc(), User.id)
            .offset(offset)
            .limit(limit + 1)
        )
    ).all()
    items = [EmperorRow(*r) for r in rows[:limit]]
    return items, len(rows) > limit


async def get_emperor(session: AsyncSession, user_id: int) -> EmperorRow | None:
    row = (await session.execute(_emperors_query(_cities_count()).where(User.id == user_id))).one_or_none()
    return EmperorRow(*row) if row else None


async def has_pending_as_attacker(session: AsyncSession, user_id: int) -> bool:
    return bool(await session.scalar(
        select(EmperorWar.id).where(EmperorWar.attacker_id == user_id, EmperorWar.status == WAR_PENDING).limit(1)
    ))


async def has_pending_as_defender(session: AsyncSession, user_id: int) -> bool:
    return bool(await session.scalar(
        select(EmperorWar.id).where(EmperorWar.defender_id == user_id, EmperorWar.status == WAR_PENDING).limit(1)
    ))


async def create_war(session: AsyncSession, *, attacker_id: int, defender_id: int, expires_at: datetime) -> int:
    war = EmperorWar(attacker_id=attacker_id, defender_id=defender_id, expires_at=expires_at)
    session.add(war)
    await session.flush()
    return war.id


async def get_pending_for_update(session: AsyncSession, war_id: int) -> EmperorWar | None:
    """Висящая война под `FOR UPDATE` — принятие и sweep не разрешат её дважды."""
    return await session.scalar(
        select(EmperorWar).where(EmperorWar.id == war_id, EmperorWar.status == WAR_PENDING).with_for_update()
    )


async def get_incoming(session: AsyncSession, defender_id: int) -> EmperorWar | None:
    return await session.scalar(
        select(EmperorWar).where(EmperorWar.defender_id == defender_id, EmperorWar.status == WAR_PENDING)
    )


async def list_expired_ids(session: AsyncSession, limit: int) -> Sequence[int]:
    return (
        await session.scalars(
            select(EmperorWar.id)
            .where(EmperorWar.status == WAR_PENDING, EmperorWar.expires_at <= func.now())
            .order_by(EmperorWar.expires_at)
            .limit(limit)
        )
    ).all()


async def city_ids_for_update(session: AsyncSession, emperor_id: int) -> list[int]:
    return list(
        (await session.scalars(
            select(City.id).where(City.emperor_id == emperor_id).order_by(City.id).with_for_update()
        )).all()
    )


async def transfer_cities(session: AsyncSession, city_ids: list[int], *, from_id: int, to_id: int) -> None:
    """Города — новому императору; персональные ставки старого для жителей этих городов
    снимаются (они теперь платят новому по его правилам — пользователь)."""
    if not city_ids:
        return
    await session.execute(update(City).where(City.id.in_(city_ids)).values(emperor_id=to_id))
    await session.execute(
        delete(EmperorTaxOverride).where(
            EmperorTaxOverride.emperor_id == from_id,
            EmperorTaxOverride.user_id.in_(select(User.id).where(User.city_id.in_(city_ids))),
        )
    )


async def count_cities(session: AsyncSession, emperor_id: int) -> int:
    return await session.scalar(select(func.count()).select_from(City).where(City.emperor_id == emperor_id))


async def finish_war(
    session: AsyncSession,
    war_id: int,
    *,
    resolution: str,
    attacker_won: bool | None,
    cities_taken: int = 0,
    treasury_taken: int = 0,
) -> None:
    await session.execute(
        update(EmperorWar)
        .where(EmperorWar.id == war_id)
        .values(
            status=WAR_RESOLVED, resolution=resolution, resolved_at=func.now(), attacker_won=attacker_won,
            cities_taken=cities_taken, treasury_taken=treasury_taken,
        )
    )


async def city_names(session: AsyncSession, city_ids: list[int]) -> list[str]:
    if not city_ids:
        return []
    return list((await session.scalars(select(City.name).where(City.id.in_(city_ids)).order_by(City.name))).all())


@dataclass(frozen=True, slots=True)
class WarHistoryRow:
    war_id: int
    as_attacker: bool
    other_username: str | None
    other_display_name: str | None
    resolution: str | None
    attacker_won: bool | None
    cities_taken: int
    treasury_taken: int
    resolved_at: datetime | None


async def list_history(session: AsyncSession, user_id: int, limit: int) -> list[WarHistoryRow]:
    """Последние завершённые войны императора (нападал или защищался) — для экрана империи."""
    other = User.__table__.alias("other")
    is_attacker = EmperorWar.attacker_id == user_id
    rows = (
        await session.execute(
            select(
                EmperorWar.id, is_attacker, other.c.username, other.c.display_name, EmperorWar.resolution,
                EmperorWar.attacker_won, EmperorWar.cities_taken, EmperorWar.treasury_taken, EmperorWar.resolved_at,
            )
            .join(other, other.c.id == func.coalesce(
                func.nullif(EmperorWar.attacker_id, user_id), EmperorWar.defender_id
            ))
            .where((EmperorWar.attacker_id == user_id) | (EmperorWar.defender_id == user_id), EmperorWar.status == WAR_RESOLVED)
            .order_by(EmperorWar.resolved_at.desc().nulls_last(), EmperorWar.id.desc())
            .limit(limit)
        )
    ).all()
    return [WarHistoryRow(*r) for r in rows]
