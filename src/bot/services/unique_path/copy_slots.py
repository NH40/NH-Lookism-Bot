"""Слоты пути Копирования (пользователь 2026-11-19).

Пути противников по-прежнему запоминаются (`battle_memory`, последние 5) — это «что можно скопировать».
Копируется только то, что лежит в слотах: игрок сам занимает слот из памяти и освобождает его; после боя
путь противника сам ложится только в СВОБОДНЫЙ слот.

2026-11-24 (пользователь): слоты — только у пути Копирования (у Бесконечной техники своя шкала — число активных
техник), и их число решает шкала Копирования: 1 сразу, +1 за каждые 25 шкалы, до 5 на полной.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.development import PATH_MEMORY_SIZE
from bot.config.path_gauge import COPY_GAUGE_PER_SLOT, COPY_SLOTS_MAX
from bot.constant.unique_path import COPYING_PATHS, PATH_COPY
from bot.db.models.development import BattleMemory, PathCopySlot, UserPath
from bot.db.models.user import User


class CopySlotError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class CopyState:
    active: bool  # активен копирующий путь
    slots: int
    taken: list[tuple[int, str, int]]  # (слот, путь, уровень)
    memory: list[tuple[int, str, int]]  # (id памяти, путь, уровень) — можно занять


def slot_count(gauge: float) -> int:
    """Слотов при шкале Копирования `gauge`: 1 + по одному за каждые 25, не больше 5."""
    return min(COPY_SLOTS_MAX, 1 + int(max(0.0, gauge) // COPY_GAUGE_PER_SLOT))


async def copy_gauge(session: AsyncSession, user_id: int) -> float | None:
    """Шкала активного пути Копирования; None — путь Копирования не активен."""
    row = (await session.execute(
        select(UserPath.gauge)
        .join(User, (User.id == UserPath.user_id) & (User.active_path == UserPath.code))
        .where(User.id == user_id, UserPath.code == PATH_COPY)
    )).one_or_none()
    return float(row[0] or 0.0) if row else None


async def taken(session: AsyncSession, user_id: int) -> list[tuple[int, str, int]]:
    rows = await session.execute(
        select(PathCopySlot.slot, PathCopySlot.path_code, PathCopySlot.path_level).where(PathCopySlot.user_id == user_id).order_by(PathCopySlot.slot)
    )
    return [(int(s), c, int(lv)) for s, c, lv in rows.all()]


async def state(session: AsyncSession, user_id: int) -> CopyState:
    gauge = await copy_gauge(session, user_id)
    rows = await session.execute(
        select(BattleMemory.id, BattleMemory.path_code, BattleMemory.path_level).where(BattleMemory.user_id == user_id)
        .order_by(BattleMemory.fought_at.desc(), BattleMemory.id.desc()).limit(PATH_MEMORY_SIZE)
    )
    memory = [(int(i), c, int(lv)) for i, c, lv in rows.all() if c not in COPYING_PATHS]
    return CopyState(gauge is not None, slot_count(gauge or 0.0), await taken(session, user_id), memory)


def _free_slot(used: list[tuple[int, str, int]], slots: int) -> int | None:
    busy = {s for s, _, _ in used}
    return next((i for i in range(1, slots + 1) if i not in busy), None)


async def take(session: AsyncSession, user_id: int, memory_id: int) -> int:
    """Занять свободный слот путём из памяти. → номер слота. Коммитит."""
    st = await state(session, user_id)
    if not st.active:
        raise CopySlotError("not_copying")
    pick = next((m for m in st.memory if m[0] == memory_id), None)
    if pick is None:
        raise CopySlotError("no_memory")
    if any(c == pick[1] for _, c, _ in st.taken):
        raise CopySlotError("already")
    slot = _free_slot(st.taken, st.slots)
    if slot is None:
        raise CopySlotError("full")
    session.add(PathCopySlot(user_id=user_id, slot=slot, path_code=pick[1], path_level=pick[2]))
    await session.commit()
    return slot


async def release(session: AsyncSession, user_id: int, slot: int) -> None:
    await session.execute(delete(PathCopySlot).where(PathCopySlot.user_id == user_id, PathCopySlot.slot == slot))
    await session.commit()


async def auto_fill(session: AsyncSession, user_id: int, opponent_id: int, path: tuple[str, int]) -> None:
    """После боя: путь противника — в свободный слот, если он есть и такого пути ещё нет. НЕ коммитит."""
    if path[0] in COPYING_PATHS:
        return
    gauge = await copy_gauge(session, user_id)
    if gauge is None:
        return
    used = await taken(session, user_id)
    if any(c == path[0] for _, c, _ in used):
        return
    slot = _free_slot(used, slot_count(gauge))
    if slot is not None:
        session.add(PathCopySlot(user_id=user_id, slot=slot, path_code=path[0], path_level=path[1], opponent_id=opponent_id))
        await session.flush()
