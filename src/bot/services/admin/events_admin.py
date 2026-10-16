"""Админка «События карты» (сервис). Мутации пишут аудит в той же транзакции."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.event import BOSS_DURATION_SECONDS, TEACHER_DURATION_SECONDS
from bot.config.school import SCHOOL_TEACHER_DURATION_SECONDS
from bot.constant.admin.events_admin import (
    AUDIT_E_REMOVE, AUDIT_E_SPAWN, KIND_BOSS_KEY, KIND_SCHOOL_KEY, KIND_TEACHER_KEY,
)
from bot.constant.event import BOSSES, EVENT_BOSS, EVENT_SCHOOL_TEACHER, EVENT_TEACHER
from bot.constant.school import SCHOOLS
from bot.constant.unique_technique import TECHNIQUES
from bot.db.models.map_event import MapEvent, MapEventEntry
from bot.db.repositories import event as event_repo
from bot.services.admin import audit
from bot.services.event import SpawnedEvent, spawn

KIND_BY_KEY = {KIND_BOSS_KEY: EVENT_BOSS, KIND_TEACHER_KEY: EVENT_TEACHER, KIND_SCHOOL_KEY: EVENT_SCHOOL_TEACHER}
CODES_BY_KIND = {EVENT_BOSS: BOSSES, EVENT_TEACHER: TECHNIQUES, EVENT_SCHOOL_TEACHER: SCHOOLS}
DURATION_BY_KIND = {
    EVENT_BOSS: BOSS_DURATION_SECONDS,
    EVENT_TEACHER: TEACHER_DURATION_SECONDS,
    EVENT_SCHOOL_TEACHER: SCHOOL_TEACHER_DURATION_SECONDS,
}


@dataclass(frozen=True, slots=True)
class EventRow:
    id: int
    kind: str
    code: str
    left_seconds: int
    clan_id: int | None
    entries: int = 0


def _left(ends_at: datetime) -> int:
    return max(0, int((ends_at - datetime.now(timezone.utc)).total_seconds()))


async def list_active(session: AsyncSession) -> list[EventRow]:
    rows = await session.scalars(select(MapEvent).where(MapEvent.ends_at > func.now()).order_by(MapEvent.kind, MapEvent.started_at))
    return [EventRow(e.id, e.kind, e.code, _left(e.ends_at), e.clan_id) for e in rows.all()]


async def get_active(session: AsyncSession, event_id: int) -> EventRow | None:
    event = await event_repo.get_active(session, event_id)
    if event is None:
        return None
    entries = await session.scalar(select(func.count()).select_from(MapEventEntry).where(MapEventEntry.event_id == event_id)) or 0
    return EventRow(event.id, event.kind, event.code, _left(event.ends_at), event.clan_id, entries)


async def remove(session: AsyncSession, admin_id: int, event_id: int) -> bool:
    event = await session.get(MapEvent, event_id)
    if event is None:
        return False
    kind, code = event.kind, event.code
    await session.execute(delete(MapEvent).where(MapEvent.id == event_id))  # записи участия — каскадом
    await audit.log(session, admin_id, AUDIT_E_REMOVE, None, {"event_id": event_id, "kind": kind, "code": code})
    await session.commit()
    return True


async def spawn_now(session: AsyncSession, admin_id: int, kind_key: str, idx: int) -> SpawnedEvent | None:
    """Запустить общее событие. None — такое же уже идёт или аргументы устарели."""
    kind = KIND_BY_KEY.get(kind_key)
    codes = CODES_BY_KIND.get(kind) if kind else None
    if codes is None or not 0 <= idx < len(codes):
        return None
    code = codes[idx]
    if code in await event_repo.active_codes(session, kind):
        return None
    spawned = await spawn(session, kind, code, DURATION_BY_KIND[kind])
    await audit.log(session, admin_id, AUDIT_E_SPAWN, None, {"event_id": spawned.id, "kind": kind, "code": code})
    await session.commit()
    return spawned
