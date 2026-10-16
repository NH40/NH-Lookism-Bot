"""Районы — владение, сид из городов, выборка для карты (репозиторий)."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.city import City
from bot.db.models.district import District
from bot.db.models.gang import Gang
from bot.db.models.user import User


@dataclass(frozen=True, slots=True)
class DistrictRow:
    id: int
    city_id: int
    number: int
    owner_id: int | None
    owner_name: str | None
    owner_gang: str | None


async def seed_districts(session: AsyncSession) -> None:
    """Один `INSERT ... SELECT generate_series` на все города разом (правило 3 — не цикл
    в Python по 207 городам × до 32 районов), `ON CONFLICT DO NOTHING` по `(city_id,
    number)` — идемпотентно, новые города из `config/city` просто получат свои районы при
    следующем сиде, существующие (и их владельцы) не трогаются. Коммитит сама — лист-
    операция, вызывается из `manager.py seed`."""
    await session.execute(
        text(
            "INSERT INTO districts (city_id, number) "
            "SELECT c.id, gs FROM cities c CROSS JOIN LATERAL generate_series(1, c.district_count) AS gs "
            "ON CONFLICT (city_id, number) DO NOTHING"
        )
    )
    await session.commit()


def _row_select():
    return (
        select(District.id, District.city_id, District.number, District.owner_id, User.display_name, Gang.name)
        .outerjoin(User, User.id == District.owner_id)
        .outerjoin(Gang, Gang.user_id == District.owner_id)
    )


async def list_by_city(session: AsyncSession, city_id: int) -> list[DistrictRow]:
    """Одним запросом с LEFT JOIN владельца и его банды — без N+1 на каждый район (правило 3)."""
    rows = await session.execute(_row_select().where(District.city_id == city_id).order_by(District.number))
    return [DistrictRow(*row) for row in rows]


async def get_row(session: AsyncSession, district_id: int) -> DistrictRow | None:
    row = (await session.execute(_row_select().where(District.id == district_id))).first()
    return DistrictRow(*row) if row else None


async def capture_from_bots(session: AsyncSession, district_id: int, user_id: int) -> bool:
    """Атомарный `UPDATE ... WHERE owner_id IS NULL` (правило 1) — если два игрока
    одновременно побили ботов одного района, район достаётся тому, чья транзакция
    закоммитилась первой, второй получит `False` (бой был, район — уже нет). НЕ коммитит
    сама — шаг составной операции атаки (`services/district.attack_district`)."""
    result = await session.execute(
        update(District)
        .where(District.id == district_id, District.owner_id.is_(None))
        .values(owner_id=user_id, captured_at=func.now())
    )
    return result.rowcount > 0


async def transfer_owner(session: AsyncSession, district_id: int, from_user_id: int, to_user_id: int) -> bool:
    """PvP-захват: `UPDATE ... WHERE owner_id = :прежний_владелец` (правило 1) — если к
    моменту записи район уже не у защитника, ничего не меняется. НЕ коммитит сама."""
    result = await session.execute(
        update(District)
        .where(District.id == district_id, District.owner_id == from_user_id)
        .values(owner_id=to_user_id, captured_at=func.now())
    )
    return result.rowcount > 0


async def count_owned(session: AsyncSession, user_id: int) -> int:
    return await session.scalar(select(func.count(District.id)).where(District.owner_id == user_id)) or 0


# --- уровень города (круг и выше) ---


@dataclass(frozen=True, slots=True)
class CityStatsRow:
    city_id: int
    name: str
    district_count: int
    bots: int
    mine: int
    owners: int  # сколько РАЗНЫХ других игроков держат районы в городе


@dataclass(frozen=True, slots=True)
class OwnerGroupRow:
    owner_id: int | None  # None — боты
    owner_name: str | None
    owner_gang: str | None
    districts: int


async def country_city_stats(session: AsyncSession, country_code: str, user_id: int) -> list[CityStatsRow]:
    """Сводка по всем городам страны одним `GROUP BY` (правило 3) — для карты страны.
    Крупные города первыми, как и при онбординге."""
    rows = await session.execute(
        select(
            City.id,
            City.name,
            City.district_count,
            func.count(District.id).filter(District.owner_id.is_(None)),
            func.count(District.id).filter(District.owner_id == user_id),
            func.count(func.distinct(District.owner_id)).filter(District.owner_id != user_id),
        )
        .join(District, District.city_id == City.id)
        .where(City.country_code == country_code)
        .group_by(City.id, City.name, City.district_count)
        .order_by(City.district_count.desc(), City.name)
    )
    return [CityStatsRow(*row) for row in rows.all()]


async def city_owner_groups(session: AsyncSession, city_id: int) -> list[OwnerGroupRow]:
    """Кто сколько районов держит в городе — одна строка на владельца (боты — `owner_id
    NULL`), с именем и бандой одним LEFT JOIN. Больше районов — выше."""
    rows = await session.execute(
        select(District.owner_id, User.display_name, Gang.name, func.count(District.id))
        .outerjoin(User, User.id == District.owner_id)
        .outerjoin(Gang, Gang.user_id == District.owner_id)
        .where(District.city_id == city_id)
        .group_by(District.owner_id, User.display_name, Gang.name)
        .order_by(func.count(District.id).desc())
    )
    return [OwnerGroupRow(*row) for row in rows.all()]


async def count_owned_in_city(session: AsyncSession, city_id: int, user_id: int) -> int:
    return await session.scalar(
        select(func.count(District.id)).where(District.city_id == city_id, District.owner_id == user_id)
    ) or 0


async def capture_all_bots_in_city(session: AsyncSession, city_id: int, user_id: int) -> int:
    """Круг разбил ботов города — забирает ВСЕ районы, что держат боты, одним `UPDATE ...
    WHERE owner_id IS NULL` (правило 1: районы, захваченные кем-то за время боя, не
    трогаются). НЕ коммитит. Возвращает, сколько районов перешло."""
    result = await session.execute(
        update(District)
        .where(District.city_id == city_id, District.owner_id.is_(None))
        .values(owner_id=user_id, captured_at=func.now())
    )
    return result.rowcount


async def transfer_all_in_city(session: AsyncSession, city_id: int, from_user_id: int, to_user_id: int) -> int:
    """PvP круга за город: все районы проигравшего в этом городе — победителю, одним
    `UPDATE ... WHERE owner_id = :проигравший` (бизнесы на них уходят вместе с районами).
    НЕ коммитит. Возвращает число перешедших районов."""
    result = await session.execute(
        update(District)
        .where(District.city_id == city_id, District.owner_id == from_user_id)
        .values(owner_id=to_user_id, captured_at=func.now())
    )
    return result.rowcount
