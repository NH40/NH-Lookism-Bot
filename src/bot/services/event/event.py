"""События на карте — появление и список (сервис). Бой с боссом — `services/district/boss.py`
(бои живут в домене district), коннект с учителем — домен уникальных техник.

raw-notes: «4 типа события… игроки получают оповещение… довольно частыми и рандомными».
Фоновый проход (`main.py: _events_loop`) раз в `EVENT_TICK_SECONDS` с заданным шансом
выпускает каждого отсутствующего босса и учителей (не больше `TEACHERS_MAX_ACTIVE`).
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config.event import (
    BOSS_DURATION_SECONDS,
    BOSS_SPAWN_CHANCE_PER_TICK,
    EVENT_PUSH_ACTIVE_DAYS,
    TEACHER_DURATION_SECONDS,
    TEACHER_SPAWN_CHANCE_PER_TICK,
    TEACHERS_MAX_ACTIVE,
)
from bot.config.clan import CLAN_BOSS_CHANCE_PER_TOWER, CLAN_TEACHER_CHANCE_PER_DOJO
from bot.constant.clan import BUILDING_DOJO, BUILDING_WATCHTOWER
from bot.db.repositories import clan as clan_repo
from bot.constant.event import BOSSES, EVENT_BOSS, EVENT_SCHOOL_TEACHER, EVENT_TEACHER
from bot.config.school import SCHOOL_TEACHER_DURATION_SECONDS, SCHOOL_TEACHER_SPAWN_CHANCE_PER_TICK
from bot.constant.school import SCHOOLS
from bot.constant.unique_technique import TECHNIQUES
from bot.db.repositories import event as event_repo

# Учителя уникальных техник (квесты — `services/unique_technique`).
TEACHERS_ENABLED = True


@dataclass(frozen=True, slots=True)
class EventView:
    id: int
    kind: str
    code: str
    ends_in_seconds: int
    won: bool = False
    connected: bool = False


@dataclass(frozen=True, slots=True)
class SpawnedEvent:
    id: int
    kind: str
    code: str
    duration_seconds: int
    clan_id: int | None = None  # клановое событие — пуш только участникам клана


def _ends_in(ends_at: datetime) -> int:
    return max(0, int((ends_at - datetime.now(timezone.utc)).total_seconds()))


async def list_active(session: AsyncSession, user_id: int) -> list[EventView]:
    return [
        EventView(e.id, e.kind, e.code, _ends_in(e.ends_at), won, connected)
        for e, won, connected in await event_repo.list_active(session, user_id)
    ]


async def spawn(session: AsyncSession, kind: str, code: str, duration_seconds: int, clan_id: int | None = None) -> SpawnedEvent:
    """Выпустить событие сейчас (фоновый проход, админка, тесты). НЕ коммитит."""
    event = await event_repo.create(session, kind, code, datetime.now(timezone.utc) + timedelta(seconds=duration_seconds), clan_id)
    return SpawnedEvent(event.id, kind, code, duration_seconds, clan_id)


async def spawn_due(
    session_factory: async_sessionmaker[AsyncSession], rng: random.Random | None = None
) -> list[SpawnedEvent]:
    """Один проход появления событий. Коммитит. → новые события (для пушей)."""
    rng = rng or random.Random()
    spawned: list[SpawnedEvent] = []
    async with session_factory() as session:
        active_bosses = await event_repo.active_codes(session, EVENT_BOSS)
        for boss in BOSSES:
            if boss not in active_bosses and rng.random() < BOSS_SPAWN_CHANCE_PER_TICK:
                spawned.append(await spawn(session, EVENT_BOSS, boss, BOSS_DURATION_SECONDS))
        if TEACHERS_ENABLED:
            active_teachers = await event_repo.active_codes(session, EVENT_TEACHER)
            free = [t for t in TECHNIQUES if t not in active_teachers]
            if free and len(active_teachers) < TEACHERS_MAX_ACTIVE and rng.random() < TEACHER_SPAWN_CHANCE_PER_TICK:
                spawned.append(await spawn(session, EVENT_TEACHER, rng.choice(free), TEACHER_DURATION_SECONDS))
        # Учитель статистов (школы) — не больше одного на карте.
        if not await event_repo.active_codes(session, EVENT_SCHOOL_TEACHER) and rng.random() < SCHOOL_TEACHER_SPAWN_CHANCE_PER_TICK:
            spawned.append(await spawn(session, EVENT_SCHOOL_TEACHER, rng.choice(SCHOOLS), SCHOOL_TEACHER_DURATION_SECONDS))
        spawned += await _spawn_clan_events(session, rng)
        await event_repo.purge_old(session)
        await session.commit()
    return spawned


async def _spawn_clan_events(session: AsyncSession, rng: random.Random) -> list[SpawnedEvent]:
    """Клановые события: Сторожевая башня клана призывает своего босса, Додзё — своего учителя
    (пользователь: здания клана — «чаще спавнятся тренера, боссы на карте»). Видны и пушатся
    только участникам клана; по одному событию вида на клан одновременно. НЕ коммитит."""
    spawned = []
    for clan_id, towers in await clan_repo.clans_with_building(session, BUILDING_WATCHTOWER):
        if not await event_repo.active_codes(session, EVENT_BOSS, clan_id) and rng.random() < CLAN_BOSS_CHANCE_PER_TOWER * towers:
            spawned.append(await spawn(session, EVENT_BOSS, rng.choice(BOSSES), BOSS_DURATION_SECONDS, clan_id))
    for clan_id, dojos in await clan_repo.clans_with_building(session, BUILDING_DOJO):
        if rng.random() >= CLAN_TEACHER_CHANCE_PER_DOJO * dojos:
            continue
        if TEACHERS_ENABLED and not await event_repo.active_codes(session, EVENT_TEACHER, clan_id):
            spawned.append(await spawn(session, EVENT_TEACHER, rng.choice(TECHNIQUES), TEACHER_DURATION_SECONDS, clan_id))
        elif not await event_repo.active_codes(session, EVENT_SCHOOL_TEACHER, clan_id):
            spawned.append(await spawn(session, EVENT_SCHOOL_TEACHER, rng.choice(SCHOOLS), SCHOOL_TEACHER_DURATION_SECONDS, clan_id))
    return spawned


async def push_recipients(session_factory: async_sessionmaker[AsyncSession]) -> list[tuple[int, list[str]]]:
    """Кому слать пуш о событии: (id, выключенные категории пушей) недавно заходивших игроков."""
    async with session_factory() as session:
        return await event_repo.recently_active_mutes(session, EVENT_PUSH_ACTIVE_DAYS)
