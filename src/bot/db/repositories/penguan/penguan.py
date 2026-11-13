"""Родословная Пеньгуана (репозиторий): временные бафы и свободный район бота."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.penguan import PenguanBuff, PenguanFallen


async def active_buffs(session: AsyncSession, user_id: int, now: datetime) -> dict[str, tuple[float, datetime]]:
    rows = await session.execute(
        select(PenguanBuff.kind, PenguanBuff.power, PenguanBuff.until).where(PenguanBuff.user_id == user_id, PenguanBuff.until > now)
    )
    return {kind: (power, until) for kind, power, until in rows}


async def set_buff(session: AsyncSession, user_id: int, kind: str, power: float, until: datetime) -> None:
    """Купить/продлить баф: новый срок и сила перекрывают старые. НЕ коммитит."""
    stmt = pg_insert(PenguanBuff).values(user_id=user_id, kind=kind, power=power, until=until)
    await session.execute(stmt.on_conflict_do_update(index_elements=[PenguanBuff.user_id, PenguanBuff.kind], set_={"power": power, "until": until}))


async def lock_bot_district(session: AsyncSession, city_id: int) -> tuple[int, int] | None:
    """Свободный район бота в городе с наименьшим номером, под блокировкой. → (id, номер)."""
    row = (await session.execute(
        text("SELECT id, number FROM districts WHERE city_id = :c AND owner_id IS NULL ORDER BY number LIMIT 1 FOR UPDATE SKIP LOCKED"),
        {"c": city_id},
    )).first()
    return (row[0], row[1]) if row else None


async def set_fallen(session: AsyncSession, user_id: int, camp: str, rows: list, until: datetime) -> None:
    """Павшие последнего боя (перезаписывают прошлые). НЕ коммитит — часть операции боя."""
    stmt = pg_insert(PenguanFallen).values(user_id=user_id, camp=camp, rows=rows, until=until)
    await session.execute(stmt.on_conflict_do_update(index_elements=[PenguanFallen.user_id], set_={"camp": camp, "rows": rows, "until": until}))


async def take_fallen(session: AsyncSession, user_id: int, now: datetime, *, delete_row: bool) -> tuple[str, list] | None:
    row = await session.scalar(select(PenguanFallen).where(PenguanFallen.user_id == user_id, PenguanFallen.until > now).with_for_update())
    if row is None:
        return None
    result = (row.camp, list(row.rows))
    if delete_row:
        await session.execute(delete(PenguanFallen).where(PenguanFallen.user_id == user_id))
    return result
