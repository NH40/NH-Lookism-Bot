"""Журнал действий, метки, память противников (репозиторий). Запись НЕ коммитит — это шаг
транзакции боя/захвата/постройки, коммитит вызывающий сервис."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.activity import ActivityLog, PlayerMark
from bot.db.models.development import BattleMemory, UserPath
from bot.db.models.user import User


async def add(session: AsyncSession, user_id: int, kind: str, line: str) -> None:
    session.add(ActivityLog(user_id=user_id, kind=kind, text=line[:256]))


async def recent(session: AsyncSession, user_id: int, kinds: Sequence[str], limit: int) -> list[tuple[datetime, str]]:
    rows = await session.execute(
        select(ActivityLog.created_at, ActivityLog.text)
        .where(ActivityLog.user_id == user_id, ActivityLog.kind.in_(kinds))
        .order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
        .limit(limit)
    )
    return [(r[0], r[1]) for r in rows.all()]


async def purge(session: AsyncSession, keep_days: int) -> None:
    await session.execute(
        text("DELETE FROM activity_log WHERE created_at < now() - make_interval(days => :d)"), {"d": keep_days}
    )


# --- метки ---


async def list_marks(session: AsyncSession, user_id: int) -> list[int]:
    rows = await session.scalars(
        select(PlayerMark.target_id).where(PlayerMark.user_id == user_id).order_by(PlayerMark.created_at)
    )
    return list(rows.all())


async def add_mark(session: AsyncSession, user_id: int, target_id: int) -> bool:
    result = await session.execute(
        pg_insert(PlayerMark).values(user_id=user_id, target_id=target_id).on_conflict_do_nothing()
    )
    return result.rowcount > 0


async def remove_mark(session: AsyncSession, user_id: int, target_id: int) -> None:
    await session.execute(delete(PlayerMark).where(PlayerMark.user_id == user_id, PlayerMark.target_id == target_id))


async def count_marks(session: AsyncSession, user_id: int) -> int:
    return await session.scalar(select(func.count()).select_from(PlayerMark).where(PlayerMark.user_id == user_id))


# --- память противников (пути Копирования / Бесконечной техники) ---


async def active_path(session: AsyncSession, user_id: int) -> tuple[str, int] | None:
    row = (
        await session.execute(
            select(User.active_path, UserPath.level)
            .join(UserPath, (UserPath.user_id == User.id) & (UserPath.code == User.active_path))
            .where(User.id == user_id)
        )
    ).one_or_none()
    return (row[0], row[1]) if row else None


async def remember(session: AsyncSession, user_id: int, opponent_id: int, path: tuple[str, int], keep: int) -> None:
    """Запомнить путь противника; хранить не больше `keep` последних."""
    session.add(BattleMemory(user_id=user_id, opponent_id=opponent_id, path_code=path[0], path_level=path[1]))
    await session.flush()
    old = (
        select(BattleMemory.id)
        .where(BattleMemory.user_id == user_id)
        .order_by(BattleMemory.fought_at.desc(), BattleMemory.id.desc())
        .offset(keep)
    )
    await session.execute(delete(BattleMemory).where(BattleMemory.id.in_(old)))
