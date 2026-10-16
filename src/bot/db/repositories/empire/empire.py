"""Император — налоги, персональные ставки, сводка империи (репозиторий).

Функции записи НЕ коммитят: начисление налога — шаг зачисления дохода бизнеса
(`services/business.accrue`), установка ставок — коммитит сервис.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.city import City
from bot.db.models.emperor_tax import EmperorTaxOverride
from bot.db.models.sabotage_log import SabotageLog
from bot.db.models.user import User


@dataclass(frozen=True, slots=True)
class TaxContext:
    emperor_id: int
    percent: int  # налог, который теряет игрок
    emperor_username: str | None
    emperor_name: str | None


@dataclass(frozen=True, slots=True)
class Subject:
    user_id: int
    username: str | None
    display_name: str | None


async def get_tax_context(session: AsyncSession, user_id: int) -> TaxContext | None:
    """Император города игрока и его ставка для этого игрока (персональная, иначе общая) —
    одним запросом. None — у города нет императора или игрок сам император."""
    emperor = User.__table__.alias("emperor")
    row = (
        await session.execute(
            select(
                City.emperor_id,
                emperor.c.empire_tax_percent,
                EmperorTaxOverride.percent,
                emperor.c.username,
                emperor.c.display_name,
            )
            .select_from(User)
            .join(City, City.id == User.city_id)
            .join(emperor, emperor.c.id == City.emperor_id)
            .outerjoin(
                EmperorTaxOverride,
                (EmperorTaxOverride.emperor_id == City.emperor_id) & (EmperorTaxOverride.user_id == User.id),
            )
            .where(User.id == user_id, City.emperor_id != user_id)
        )
    ).one_or_none()
    if row is None:
        return None
    emperor_id, global_percent, personal_percent, username, name = row
    return TaxContext(
        emperor_id=emperor_id,
        percent=personal_percent if personal_percent is not None else global_percent,
        emperor_username=username,
        emperor_name=name,
    )


async def get_override(session: AsyncSession, emperor_id: int, user_id: int) -> int | None:
    return await session.scalar(
        select(EmperorTaxOverride.percent).where(
            EmperorTaxOverride.emperor_id == emperor_id, EmperorTaxOverride.user_id == user_id
        )
    )


async def credit_emperor(session: AsyncSession, emperor_id: int, amount: int) -> None:
    """Налог + пассивный бонус — в кошелёк императора (казна = кошелёк, пользователь
    2026-10-01) и в счётчик собранного."""
    if amount <= 0:
        return
    await session.execute(
        update(User)
        .where(User.id == emperor_id)
        .values(nh_coins=User.nh_coins + amount, empire_collected=User.empire_collected + amount)
    )


async def set_global_rate(session: AsyncSession, emperor_id: int, percent: int) -> None:
    await session.execute(update(User).where(User.id == emperor_id).values(empire_tax_percent=percent))


async def set_override(session: AsyncSession, emperor_id: int, user_id: int, percent: int) -> None:
    await session.execute(
        pg_insert(EmperorTaxOverride)
        .values(emperor_id=emperor_id, user_id=user_id, percent=percent)
        .on_conflict_do_update(
            index_elements=[EmperorTaxOverride.emperor_id, EmperorTaxOverride.user_id], set_={"percent": percent}
        )
    )


async def delete_override(session: AsyncSession, emperor_id: int, user_id: int) -> None:
    await session.execute(
        delete(EmperorTaxOverride).where(
            EmperorTaxOverride.emperor_id == emperor_id, EmperorTaxOverride.user_id == user_id
        )
    )


async def find_subject(session: AsyncSession, emperor_id: int, username: str) -> Subject | None:
    """Игрок империи по юзернейму (без @, регистр не важен) — только из городов императора."""
    row = (
        await session.execute(
            select(User.id, User.username, User.display_name)
            .join(City, City.id == User.city_id)
            .where(
                City.emperor_id == emperor_id,
                User.id != emperor_id,
                func.lower(User.username) == username.lstrip("@").lower(),
            )
            .limit(1)
        )
    ).one_or_none()
    return Subject(*row) if row else None


@dataclass(frozen=True, slots=True)
class EmpireStats:
    cities: int
    players: int
    tax_percent: int
    collected: int
    nh_coins: int
    overrides: list[tuple[str | None, str | None, int]]  # (username, имя, ставка)
    overrides_total: int
    sabotage_total: int = 0  # попыток саботажа за последние `sabotage_hours`
    sabotage_success: int = 0


async def empire_stats(
    session: AsyncSession, emperor_id: int, overrides_limit: int, sabotage_hours: int = 0
) -> EmpireStats:
    cities = await session.scalar(select(func.count()).select_from(City).where(City.emperor_id == emperor_id))
    players = await session.scalar(
        select(func.count())
        .select_from(User)
        .join(City, City.id == User.city_id)
        .where(City.emperor_id == emperor_id, User.id != emperor_id)
    )
    me = (
        await session.execute(
            select(User.empire_tax_percent, User.empire_collected, User.nh_coins).where(User.id == emperor_id)
        )
    ).one()
    rows = await session.execute(
        select(User.username, User.display_name, EmperorTaxOverride.percent)
        .join(User, User.id == EmperorTaxOverride.user_id)
        .where(EmperorTaxOverride.emperor_id == emperor_id)
        .order_by(EmperorTaxOverride.percent.desc())
        .limit(overrides_limit)
    )
    total = await session.scalar(
        select(func.count()).select_from(EmperorTaxOverride).where(EmperorTaxOverride.emperor_id == emperor_id)
    )
    sabotage_total, sabotage_success = (
        await count_recent_sabotage(session, emperor_id, sabotage_hours) if sabotage_hours else (0, 0)
    )
    return EmpireStats(
        cities=cities, players=players, tax_percent=me[0], collected=me[1], nh_coins=me[2],
        overrides=[tuple(r) for r in rows.all()], overrides_total=total,
        sabotage_total=sabotage_total, sabotage_success=sabotage_success,
    )


# --- саботаж ---


async def emperor_coins(session: AsyncSession, emperor_id: int, *, for_update: bool = False) -> int:
    """Кошелёк императора под `FOR UPDATE` — кража из казны считает долю от текущего
    остатка и списывает в одной транзакции (правило 1)."""
    stmt = select(User.nh_coins).where(User.id == emperor_id)
    return await session.scalar(stmt.with_for_update() if for_update else stmt) or 0


async def move_coins(session: AsyncSession, from_id: int, to_id: int, amount: int) -> None:
    """Перевод NHCoin; строка `from_id` уже заблокирована вызывающим (`emperor_coins(for_update=True)`)."""
    await session.execute(update(User).where(User.id == from_id).values(nh_coins=User.nh_coins - amount))
    await session.execute(update(User).where(User.id == to_id).values(nh_coins=User.nh_coins + amount))


async def add_sabotage_log(
    session: AsyncSession,
    *,
    emperor_id: int,
    saboteur_id: int,
    action: str,
    success: bool,
    amount: int,
    card_code: str | None,
) -> None:
    session.add(
        SabotageLog(
            emperor_id=emperor_id, saboteur_id=saboteur_id, action=action, success=success,
            amount=amount, card_code=card_code,
        )
    )


async def count_recent_sabotage(session: AsyncSession, emperor_id: int, hours: int) -> tuple[int, int]:
    """(всего попыток, удачных) против императора за последние `hours` — одним запросом."""
    row = (
        await session.execute(
            select(func.count(), func.count().filter(SabotageLog.success))
            .where(
                SabotageLog.emperor_id == emperor_id,
                SabotageLog.created_at >= func.now() - timedelta(hours=hours),
            )
        )
    ).one()
    return int(row[0]), int(row[1])
