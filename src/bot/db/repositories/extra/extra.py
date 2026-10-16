"""Статисты — стопки по (лагерь, ранг, звёзды, уровень тренировки), не по одной строке
на статиста (см. `db/models/extra.py` — масштаб "сотни миллиардов на игрока").
"""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.extra import Extra


async def add_to_stack(
    session: AsyncSession,
    *,
    user_id: int,
    camp: str,
    rank: str,
    stars: int = 0,
    training_level: int = 0,
    quantity: int,
    school: str = "",
    school_level: int = 0,
) -> None:
    """`quantity` может быть отрицательным (списание: перенос части стопки при
    тренировке/смене лагеря, гибель в бою) — НЕ коммитит сама (правило 10, внутренний
    шаг составной операции). `ON CONFLICT DO UPDATE quantity = quantity + :delta` —
    один атомарный upsert вместо "прочитать, потом обновить" (правило 1). `camp`
    обязателен (без дефолта) — перепутать лагерь при переносе молча было бы худшей
    ошибкой, чем явно передать его в каждом вызове."""
    if quantity == 0:
        return
    stmt = (
        pg_insert(Extra)
        .values(
            user_id=user_id, camp=camp, rank=rank, stars=stars, training_level=training_level, quantity=quantity,
            school=school, school_level=school_level,
        )
        .on_conflict_do_update(
            index_elements=[
                Extra.user_id, Extra.camp, Extra.rank, Extra.stars, Extra.training_level, Extra.school, Extra.school_level,
            ],
            set_={"quantity": Extra.quantity + quantity},
        )
    )
    await session.execute(stmt)


async def list_stacks(
    session: AsyncSession, user_id: int, *, camp: str | None = None, for_update: bool = False
) -> Sequence[Extra]:
    stmt = select(Extra).where(Extra.user_id == user_id, Extra.quantity > 0)
    if camp is not None:
        stmt = stmt.where(Extra.camp == camp)
    if for_update:
        stmt = stmt.with_for_update()
    return (await session.scalars(stmt)).all()


async def get_stack_for_update(
    session: AsyncSession, *, user_id: int, camp: str, rank: str, stars: int, training_level: int,
    school: str = "", school_level: int = 0,
) -> Extra | None:
    """Одна стопка под `FOR UPDATE` — перенос части отряда между лагерями читает остаток и
    списывает в одной транзакции (правило 1), параллельная тренировка/бой не собьют счёт."""
    return await session.scalar(
        select(Extra)
        .where(
            Extra.user_id == user_id,
            Extra.camp == camp,
            Extra.rank == rank,
            Extra.stars == stars,
            Extra.training_level == training_level,
            Extra.school == school,
            Extra.school_level == school_level,
        )
        .with_for_update()
    )


async def total_quantity(session: AsyncSession, user_id: int) -> int:
    return await session.scalar(select(func.coalesce(func.sum(Extra.quantity), 0)).where(Extra.user_id == user_id))
