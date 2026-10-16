"""Мастерство — состояние цепочки «Преодоление стены» (репозиторий).

Функции записи НЕ коммитят (кроме явно отмеченных): шаги составных операций сервиса.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.characteristic import MASTERY_ENDURANCE, MASTERY_SPEED, MASTERY_STRENGTH, MASTERY_TECHNIQUE
from bot.constant.mastery import QUEST_ACTIVE, QUEST_PENDING
from bot.db.models.mastery_quest import MasteryQuest
from bot.db.models.user import User

_MASTERY_COLUMNS = {
    MASTERY_STRENGTH: User.mastery_strength,
    MASTERY_SPEED: User.mastery_speed,
    MASTERY_ENDURANCE: User.mastery_endurance,
    MASTERY_TECHNIQUE: User.mastery_technique,
}


async def get(session: AsyncSession, user_id: int, *, for_update: bool = False) -> MasteryQuest | None:
    stmt = select(MasteryQuest).where(MasteryQuest.user_id == user_id)
    if for_update:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    return await session.scalar(stmt)


async def create_pending(session: AsyncSession, user_id: int, available_at: datetime) -> bool:
    """Первый этап — `ON CONFLICT DO NOTHING`: повторная проверка условия не создаст вторую
    цепочку и не сдвинет уже назначенное время."""
    result = await session.execute(
        pg_insert(MasteryQuest)
        .values(user_id=user_id, stage=1, status=QUEST_PENDING, available_at=available_at)
        .on_conflict_do_nothing()
    )
    return result.rowcount > 0


async def list_due_pending(session: AsyncSession, limit: int) -> list[int]:
    rows = await session.scalars(
        select(MasteryQuest.user_id)
        .where(MasteryQuest.status == QUEST_PENDING, MasteryQuest.available_at <= func.now())
        .order_by(MasteryQuest.available_at)
        .limit(limit)
    )
    return list(rows)


async def activate(session: AsyncSession, user_id: int, tom_power: int) -> bool:
    """`pending → active` атомарно (`WHERE status='pending' AND available_at <= now()`):
    sweep и ленивая активация с экрана не активируют этап дважды."""
    result = await session.execute(
        update(MasteryQuest)
        .where(
            MasteryQuest.user_id == user_id,
            MasteryQuest.status == QUEST_PENDING,
            MasteryQuest.available_at <= func.now(),
        )
        .values(status=QUEST_ACTIVE, tom_power=tom_power)
    )
    return result.rowcount > 0


async def bump_mastery(session: AsyncSession, user_id: int, mastery: str, *, cap: int) -> bool:
    """Ступень мастерства +1, но не выше `cap` (ступень текущего этапа) — условием в UPDATE."""
    col = _MASTERY_COLUMNS[mastery]
    result = await session.execute(update(User).where(User.id == user_id, col < cap).values({col: col + 1}))
    return result.rowcount > 0
