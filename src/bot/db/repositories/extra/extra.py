"""Статисты — стопки по (ранг, звёзды, уровень тренировки), не по одной строке на
статиста (см. `db/models/extra.py` — переработано 2026-09-21 под масштаб "сотни
миллиардов на игрока", по одной строке за раз это физически нереализуемо).
"""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.extra import Extra


async def add_to_stack(
    session: AsyncSession, *, user_id: int, rank: str, stars: int = 0, training_level: int = 0, quantity: int
) -> None:
    """`quantity` может быть отрицательным (списание при переносе части стопки в
    тренировке, см. `services/training`) — НЕ коммитит сама (правило 10, внутренний
    шаг составной операции: вербовка/тренировка коммитят один раз сами, после всех
    шагов). `ON CONFLICT DO UPDATE quantity = quantity + excluded.quantity` — один
    атомарный upsert вместо "прочитать, потом обновить" (правило 1)."""
    if quantity == 0:
        return
    stmt = (
        pg_insert(Extra)
        .values(user_id=user_id, rank=rank, stars=stars, training_level=training_level, quantity=quantity)
        .on_conflict_do_update(
            index_elements=[Extra.user_id, Extra.rank, Extra.stars, Extra.training_level],
            set_={"quantity": Extra.quantity + quantity},
        )
    )
    await session.execute(stmt)


async def list_stacks(session: AsyncSession, user_id: int, *, for_update: bool = False) -> Sequence[Extra]:
    stmt = select(Extra).where(Extra.user_id == user_id, Extra.quantity > 0)
    if for_update:
        stmt = stmt.with_for_update()
    return (await session.scalars(stmt)).all()


async def total_quantity(session: AsyncSession, user_id: int) -> int:
    return await session.scalar(select(func.coalesce(func.sum(Extra.quantity), 0)).where(Extra.user_id == user_id))
