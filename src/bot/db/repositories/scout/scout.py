"""Отчёты разведки (репозиторий). Запись не коммитит — коммитит сервис."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.scout_report import ScoutReport


async def save(session: AsyncSession, viewer_id: int, target_id: int, payload: dict) -> datetime:
    now = datetime.now(timezone.utc)
    stmt = pg_insert(ScoutReport).values(viewer_id=viewer_id, target_id=target_id, created_at=now, payload=payload)
    await session.execute(stmt.on_conflict_do_update(
        index_elements=[ScoutReport.viewer_id, ScoutReport.target_id], set_={"created_at": now, "payload": payload},
    ))
    return now


async def get(session: AsyncSession, viewer_id: int, target_id: int) -> ScoutReport | None:
    return await session.get(ScoutReport, (viewer_id, target_id))


async def exists(session: AsyncSession, viewer_id: int, target_id: int) -> bool:
    row = await session.scalar(
        select(ScoutReport.target_id).where(ScoutReport.viewer_id == viewer_id, ScoutReport.target_id == target_id)
    )
    return row is not None


async def recent(session: AsyncSession, viewer_id: int, limit: int) -> Sequence[ScoutReport]:
    return (await session.scalars(
        select(ScoutReport).where(ScoutReport.viewer_id == viewer_id).order_by(ScoutReport.created_at.desc()).limit(limit)
    )).all()


async def delete_for(session: AsyncSession, viewer_id: int, target_id: int) -> None:
    await session.execute(delete(ScoutReport).where(ScoutReport.viewer_id == viewer_id, ScoutReport.target_id == target_id))
