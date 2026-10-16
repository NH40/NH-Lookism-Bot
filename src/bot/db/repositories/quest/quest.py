"""Ежедневные задания (репозиторий). Функции записи НЕ коммитят — шаги транзакции сервиса
(`services/quest`), в т.ч. чужой: прогресс растёт внутри транзакции действия игрока."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.quest import DailyQuest, DailyQuestState

_LOCK_STATE_SQL = text(
    """
    INSERT INTO daily_quest_states (user_id, day) VALUES (:u, :day)
    ON CONFLICT (user_id) DO NOTHING
    """
)

_ADVANCE_SQL = text(
    """
    UPDATE daily_quests
    SET progress = LEAST(progress + :n, target),
        completed_at = CASE WHEN progress + :n >= target THEN now() END
    WHERE user_id = :u AND day = :day AND task = :task AND completed_at IS NULL
    RETURNING slot, xp, completed_at IS NOT NULL
    """
)


async def state_day(session: AsyncSession, user_id: int) -> date | None:
    return (
        await session.execute(select(DailyQuestState.day).where(DailyQuestState.user_id == user_id))
    ).scalar_one_or_none()


async def lock_state(session: AsyncSession, user_id: int, today: date) -> DailyQuestState:
    """Состояние дня под `FOR UPDATE` (создаётся при первом обращении)."""
    await session.execute(_LOCK_STATE_SQL, {"u": user_id, "day": today})
    return (
        await session.execute(
            select(DailyQuestState).where(DailyQuestState.user_id == user_id).with_for_update().execution_options(populate_existing=True)
        )
    ).scalar_one()


async def list_day(session: AsyncSession, user_id: int, day: date) -> Sequence[DailyQuest]:
    return (
        await session.execute(
            select(DailyQuest).where(DailyQuest.user_id == user_id, DailyQuest.day == day).order_by(DailyQuest.slot).execution_options(populate_existing=True)
        )
    ).scalars().all()


async def codes_since(session: AsyncSession, user_id: int, since: date) -> set[str]:
    rows = await session.execute(
        select(DailyQuest.code).where(DailyQuest.user_id == user_id, DailyQuest.day >= since)
    )
    return set(rows.scalars().all())


async def purge_before(session: AsyncSession, user_id: int, before: date) -> None:
    """Старые дни больше не нужны (кроме окна «не повторять») — таблица остаётся маленькой."""
    await session.execute(delete(DailyQuest).where(DailyQuest.user_id == user_id, DailyQuest.day < before))


async def delete_slots(session: AsyncSession, user_id: int, day: date, slots: Sequence[int]) -> None:
    await session.execute(
        delete(DailyQuest).where(DailyQuest.user_id == user_id, DailyQuest.day == day, DailyQuest.slot.in_(list(slots)))
    )


async def insert(session: AsyncSession, user_id: int, day: date, rows: Sequence[tuple[int, str, str, int, int]]) -> None:
    """rows: (слот, код, событие, цель, опыт)."""
    session.add_all(
        DailyQuest(user_id=user_id, day=day, slot=slot, code=code, task=task, target=target, xp=xp, progress=0)
        for slot, code, task, target, xp in rows
    )
    await session.flush()


async def advance(session: AsyncSession, user_id: int, day: date, task: str, n: int) -> list[tuple[int, int]]:
    """Прогресс заданий дня с этим событием. → [(слот, опыт)] заданий, выполненных этим вызовом."""
    rows = await session.execute(_ADVANCE_SQL, {"u": user_id, "day": day, "task": task, "n": n})
    return [(slot, xp) for slot, xp, done in rows.all() if done]


async def add_completed(session: AsyncSession, user_id: int, k: int) -> int:
    """+k к счётчику выполненных за день (атомарно). → новое значение."""
    return (
        await session.execute(
            text("UPDATE daily_quest_states SET completed = completed + :k WHERE user_id = :u RETURNING completed"),
            {"u": user_id, "k": k},
        )
    ).scalar_one()
