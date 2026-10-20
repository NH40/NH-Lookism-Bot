"""Бизнесы на районе — кофе/зал/магазин/нелегальный рынок/парламент, прокачка уровень/вместимость (репозиторий).

Здание не хранит владельца — владелец района и есть владелец бизнеса (см.
`db/models/business.py`), поэтому все выборки "бизнесы игрока" — JOIN с `districts`
по `owner_id`, агрегация в SQL (правило 3). Кошелёк (`users.nh_coins` и прокачка) —
здесь же, а не в `db/repositories/user`: эти колонки читает и пишет только бизнес.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.business import UPGRADE_CAPACITY, UPGRADE_LEVEL
from bot.db.models.business import Business
from bot.db.models.city import City
from bot.db.models.district import District
from bot.db.models.user import User


@dataclass(frozen=True, slots=True)
class WalletRow:
    nh_coins: int
    coins_accrued_at: datetime
    business_level: int
    business_capacity: int


@dataclass(frozen=True, slots=True)
class OwnedDistrictRow:
    district_id: int
    city_name: str
    number: int
    buildings: int


def _wallet_select():
    return select(User.nh_coins, User.coins_accrued_at, User.business_level, User.business_capacity)


async def get_wallet(session: AsyncSession, user_id: int, *, for_update: bool = False) -> WalletRow | None:
    stmt = _wallet_select().where(User.id == user_id)
    if for_update:
        stmt = stmt.with_for_update()
    row = (await session.execute(stmt)).one_or_none()
    return WalletRow(*row) if row is not None else None


async def add_coins(session: AsyncSession, user_id: int, amount: int) -> None:
    """Начислить NHCoin (возврат «Отката», удвоение «Двойной смены»). НЕ коммитит."""
    await session.execute(update(User).where(User.id == user_id).values(nh_coins=User.nh_coins + amount))


async def credit_accrual(session: AsyncSession, user_id: int, *, amount: int, accrued_at: datetime) -> None:
    """Зачисление накопленного дохода и сдвиг отметки начисления. Вызывается только под
    `get_wallet(for_update=True)` той же транзакции. НЕ коммитит (правило 10)."""
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(nh_coins=User.nh_coins + amount, coins_accrued_at=accrued_at)
    )


async def spend_coins(session: AsyncSession, user_id: int, amount: int) -> bool:
    """`UPDATE ... WHERE nh_coins >= :amount` (правило 1). НЕ коммитит."""
    result = await session.execute(
        update(User).where(User.id == user_id, User.nh_coins >= amount).values(nh_coins=User.nh_coins - amount)
    )
    return result.rowcount > 0


_UPGRADE_COLUMNS = {UPGRADE_LEVEL: User.business_level, UPGRADE_CAPACITY: User.business_capacity}


async def bump_upgrade(session: AsyncSession, user_id: int, *, kind: str, current: int, cost: int) -> bool:
    """Повышает `business_level`/`business_capacity` на 1 и списывает цену ОДНИМ `UPDATE`
    с условием на текущий уровень и баланс — двойной клик не купит два уровня по цене
    одного и не уйдёт в минус. НЕ коммитит."""
    col = _UPGRADE_COLUMNS[kind]
    result = await session.execute(
        update(User)
        .where(User.id == user_id, col == current, User.nh_coins >= cost)
        .values({col: col + 1, User.nh_coins: User.nh_coins - cost})
    )
    return result.rowcount > 0


def _owned_by(user_id: int):
    """Здания игрока: на его районах ИЛИ в его владениях (у императора, район освобождён)."""
    return or_(District.owner_id == user_id, Business.holder_id == user_id)


async def count_by_type(session: AsyncSession, user_id: int) -> dict[str, int]:
    rows = await session.execute(
        select(Business.type, func.count())
        .outerjoin(District, District.id == Business.district_id)
        .where(_owned_by(user_id))
        .group_by(Business.type)
    )
    return {type_: count for type_, count in rows.all()}


async def count_type(session: AsyncSession, user_id: int, type_: str) -> int:
    return await session.scalar(
        select(func.count())
        .select_from(Business)
        .outerjoin(District, District.id == Business.district_id)
        .where(_owned_by(user_id), Business.type == type_)
    )


async def count_by_type_on_district(session: AsyncSession, district_id: int) -> dict[str, int]:
    rows = await session.execute(
        select(Business.type, func.count()).where(Business.district_id == district_id).group_by(Business.type)
    )
    return {type_: count for type_, count in rows.all()}


async def count_by_type_per_district(session: AsyncSession, user_id: int) -> dict[int, dict[str, int]]:
    """Здания по типам для ВСЕХ районов игрока — один запрос вместо N."""
    rows = await session.execute(
        select(Business.district_id, Business.type, func.count())
        .join(District, District.id == Business.district_id)
        .where(District.owner_id == user_id)
        .group_by(Business.district_id, Business.type)
    )
    result: dict[int, dict[str, int]] = {}
    for district_id, type_, count in rows.all():
        result.setdefault(district_id, {})[type_] = count
    return result


async def list_owned_districts(session: AsyncSession, user_id: int) -> list[OwnedDistrictRow]:
    """Районы игрока с числом зданий на каждом — одним запросом (LEFT JOIN + GROUP BY).
    С городом: у круга районы в нескольких городах, номера районов между ними повторяются."""
    rows = await session.execute(
        select(District.id, City.name, District.number, func.count(Business.id))
        .join(City, City.id == District.city_id)
        .outerjoin(Business, Business.district_id == District.id)
        .where(District.owner_id == user_id)
        .group_by(District.id, City.name, District.number)
        .order_by(City.name, District.number)
    )
    return [OwnedDistrictRow(*row) for row in rows.all()]


async def lock_owned_district(session: AsyncSession, district_id: int, user_id: int) -> District | None:
    """`SELECT ... FOR UPDATE` района с проверкой владельца — сериализует стройку на одном
    районе (две параллельные стройки не займут одно свободное место дважды) и не даёт
    району сменить владельца посреди стройки (PvP-захват ждёт этот лок)."""
    return await session.scalar(
        select(District).where(District.id == district_id, District.owner_id == user_id).with_for_update()
    )


async def create(session: AsyncSession, district_id: int, type_: str) -> None:
    """НЕ коммитит (правило 10 — часть стройки: списание + здание одним commit)."""
    session.add(Business(district_id=district_id, type=type_))
    await session.flush()


async def lock_owned_districts(session: AsyncSession, user_id: int) -> list[District]:
    """Все районы игрока под `FOR UPDATE` (порядок по id — без взаимных блокировок) —
    массовая стройка, тот же смысл, что `lock_owned_district`."""
    rows = await session.scalars(
        select(District).where(District.owner_id == user_id).order_by(District.id).with_for_update()
    )
    return list(rows.all())


async def create_many(session: AsyncSession, items: list[tuple[int, str]]) -> None:
    """Пачка зданий одним INSERT (правило 3). НЕ коммитит."""
    if items:
        await session.execute(insert(Business), [{"district_id": d, "type": t} for d, t in items])


async def delete_on_district(session: AsyncSession, district_id: int, type_: str | None) -> int:
    """Снести одно здание типа `type_` (последнее построенное) или все здания района (`None`).
    → сколько снесено. НЕ коммитит."""
    if type_ is None:
        result = await session.execute(delete(Business).where(Business.district_id == district_id))
        return result.rowcount or 0
    one = (
        select(Business.id).where(Business.district_id == district_id, Business.type == type_)
        .order_by(Business.id.desc()).limit(1).scalar_subquery()
    )
    result = await session.execute(delete(Business).where(Business.id == one))
    return result.rowcount or 0


async def delete_on_owned_districts(session: AsyncSession, user_id: int, type_: str | None) -> int:
    """Снести все здания (или все типа `type_`) на ВСЕХ районах игрока одним DELETE; владения
    императора не трогает. → сколько снесено. НЕ коммитит."""
    cond = Business.district_id.in_(select(District.id).where(District.owner_id == user_id))
    if type_ is not None:
        cond = cond & (Business.type == type_)
    result = await session.execute(delete(Business).where(cond))
    return result.rowcount or 0
