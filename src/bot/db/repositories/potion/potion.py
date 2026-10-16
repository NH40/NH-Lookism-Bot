"""Зелья (репозиторий). Функции записи НЕ коммитят — коммитит сервис."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.potion import UserPotion


async def list_for_user(session: AsyncSession, user_id: int) -> Sequence[UserPotion]:
    return (await session.scalars(select(UserPotion).where(UserPotion.user_id == user_id))).all()


async def active_for_user(session: AsyncSession, user_id: int) -> Sequence[tuple[str, int]]:
    """(вид, тир) действующих зелий — для Build (один лёгкий запрос по PK-префиксу)."""
    rows = await session.execute(
        select(UserPotion.kind, UserPotion.tier).where(
            UserPotion.user_id == user_id, UserPotion.tier > 0, UserPotion.expires_at > func.now()
        )
    )
    return [(r[0], r[1]) for r in rows.all()]


async def get_window(session: AsyncSession, user_id: int, kind: str) -> tuple[int, datetime, datetime] | None:
    row = (
        await session.execute(
            select(UserPotion.tier, UserPotion.started_at, UserPotion.expires_at).where(
                UserPotion.user_id == user_id, UserPotion.kind == kind
            )
        )
    ).one_or_none()
    return (row[0], row[1], row[2]) if row and row[0] > 0 else None


async def drink(session: AsyncSession, user_id: int, kind: str, tier: int, started_at: datetime, expires_at: datetime) -> None:
    """Выпить: новый тир и окно заменяют прежние (один эффект на вид), авто-настройка цела."""
    stmt = pg_insert(UserPotion).values(user_id=user_id, kind=kind, tier=tier, started_at=started_at, expires_at=expires_at)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=[UserPotion.user_id, UserPotion.kind],
            set_={"tier": tier, "started_at": started_at, "expires_at": expires_at},
        )
    )


async def set_auto(session: AsyncSession, user_id: int, kind: str, tier: int) -> None:
    stmt = pg_insert(UserPotion).values(user_id=user_id, kind=kind, tier=0, auto_tier=tier)
    await session.execute(
        stmt.on_conflict_do_update(index_elements=[UserPotion.user_id, UserPotion.kind], set_={"auto_tier": tier})
    )


async def count_auto(session: AsyncSession, user_id: int, exclude_kind: str) -> int:
    return int(
        await session.scalar(
            select(func.count()).where(UserPotion.user_id == user_id, UserPotion.auto_tier > 0, UserPotion.kind != exclude_kind)
        )
        or 0
    )


async def due_auto(session: AsyncSession, horizon: datetime, limit: int = 500) -> Sequence[tuple[int, str, int]]:
    """(игрок, вид, тир) авто-зелий, которые кончились или кончатся до `horizon`."""
    rows = await session.execute(
        select(UserPotion.user_id, UserPotion.kind, UserPotion.auto_tier)
        .where(UserPotion.auto_tier > 0, UserPotion.expires_at <= horizon)
        .order_by(UserPotion.expires_at)
        .limit(limit)
    )
    return [(r[0], r[1], r[2]) for r in rows.all()]


async def disable_auto(session: AsyncSession, user_id: int, kind: str) -> None:
    await session.execute(
        update(UserPotion).where(UserPotion.user_id == user_id, UserPotion.kind == kind).values(auto_tier=0)
    )
