"""Задания систем развития (репозиторий). Функции записи НЕ коммитят: `emit` — шаг
транзакции боя/тренировки/вербовки, создание и закрытие — коммитит сервис-владелец."""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.dev_quest import STATUS_ACTIVE, STATUS_DONE
from bot.db.models.dev_quest import DevQuest

# Прогресс задания растёт одним UPDATE по всем активным квестам игрока, где это задание
# есть, с потолком «сколько нужно» — без чтения в Python (правило 1, правило 3).
_EMIT_SQL = text(
    """
    UPDATE dev_quests
    SET progress = jsonb_set(
        progress, ARRAY[:task],
        to_jsonb(LEAST(COALESCE((progress->>:task)::int, 0) + :n, (tasks->>:task)::int))
    )
    WHERE user_id = :user_id AND status = :active AND tasks ? :task
    """
)


async def create(session: AsyncSession, user_id: int, kind: str, ref: str, tasks: dict[str, int]) -> bool:
    """Новый активный квест. False — такой уже идёт (частичный уникальный индекс)."""
    result = await session.execute(
        pg_insert(DevQuest).values(user_id=user_id, kind=kind, ref=ref, tasks=tasks, progress={}).on_conflict_do_nothing()
    )
    return result.rowcount > 0


async def list_active(session: AsyncSession, user_id: int, kind: str | None = None) -> Sequence[DevQuest]:
    stmt = select(DevQuest).where(DevQuest.user_id == user_id, DevQuest.status == STATUS_ACTIVE)
    if kind is not None:
        stmt = stmt.where(DevQuest.kind == kind)
    return (await session.scalars(stmt.order_by(DevQuest.created_at))).all()


async def get_active_for_update(session: AsyncSession, user_id: int, kind: str, ref: str = "") -> DevQuest | None:
    return await session.scalar(
        select(DevQuest)
        .where(DevQuest.user_id == user_id, DevQuest.kind == kind, DevQuest.ref == ref, DevQuest.status == STATUS_ACTIVE)
        .with_for_update()
    )


async def emit(session: AsyncSession, user_id: int, task: str, n: int = 1) -> None:
    await session.execute(_EMIT_SQL, {"user_id": user_id, "task": task, "n": n, "active": STATUS_ACTIVE})


async def mark_done(session: AsyncSession, quest_id: int) -> bool:
    result = await session.execute(
        update(DevQuest).where(DevQuest.id == quest_id, DevQuest.status == STATUS_ACTIVE).values(status=STATUS_DONE)
    )
    return result.rowcount > 0


async def delete_for_user(session: AsyncSession, user_id: int, kinds: Sequence[str]) -> None:
    """Сброс (удаление банды): квесты этих видов снимаются."""
    await session.execute(
        text("DELETE FROM dev_quests WHERE user_id = :u AND kind = ANY(:k)"), {"u": user_id, "k": list(kinds)}
    )
