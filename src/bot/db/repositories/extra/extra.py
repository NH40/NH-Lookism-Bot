"""Статисты — стопки по (лагерь, ранг, звёзды, уровень тренировки), не по одной строке
на статиста (см. `db/models/extra.py` — масштаб "сотни миллиардов на игрока").
"""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select, text
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


# (user_id, camp, rank, stars, training_level, school, school_level)
StackKey = tuple[int, str, str, int, int, str, int]

_ADD_MANY_SQL = text(
    """
    INSERT INTO extras (user_id, camp, rank, stars, training_level, school, school_level, quantity)
    SELECT * FROM unnest(
        CAST(:u AS bigint[]), CAST(:c AS varchar[]), CAST(:r AS varchar[]), CAST(:s AS int[]),
        CAST(:t AS int[]), CAST(:sc AS varchar[]), CAST(:sl AS int[]), CAST(:q AS bigint[])
    )
    ON CONFLICT (user_id, camp, rank, stars, training_level, school, school_level)
    DO UPDATE SET quantity = extras.quantity + EXCLUDED.quantity
    """
)


def stack_key(
    user_id: int, camp: str, rank: str, stars: int = 0, training_level: int = 0, school: str = "", school_level: int = 0
) -> StackKey:
    return (user_id, camp, rank, stars, training_level, school, school_level)


async def add_to_stacks(session: AsyncSession, deltas: dict[StackKey, int]) -> None:
    """То же, что `add_to_stack`, но для многих стопок ОДНИМ запросом (хотфикс 2026-11-12: у
    крупных игроков десятки тысяч стопок, и перевод лагеря запросом на стопку держал
    транзакцию минутами, выедая весь пул соединений). Ключи разные по построению (dict), так
    что `ON CONFLICT` не трогает одну строку дважды; сортировка — один порядок блокировок.
    НЕ коммитит."""
    rows = sorted((key, q) for key, q in deltas.items() if q)
    if not rows:
        return
    u, c, r, s, t, sc, sl = (list(col) for col in zip(*(key for key, _ in rows)))
    await session.execute(
        _ADD_MANY_SQL, {"u": u, "c": c, "r": r, "s": s, "t": t, "sc": sc, "sl": sl, "q": [q for _, q in rows]}
    )


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
    # SUM(bigint) в Postgres — numeric: без int() вызывающие падали на Decimal * float (саботаж).
    return int(await session.scalar(select(func.coalesce(func.sum(Extra.quantity), 0)).where(Extra.user_id == user_id)) or 0)
