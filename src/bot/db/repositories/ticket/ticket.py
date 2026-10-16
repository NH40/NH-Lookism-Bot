"""Тикеты на вербовку уников — ленивый реген + атомарное списание (репозиторий).

Тот же приём, что в UAP (`services/ticket`): регенерация считается НЕ фоновым таском, а
при каждом обращении, одним `UPDATE` над строкой, заблокированной `FOR UPDATE` в CTE —
списание и реген не могут разъехаться, двойной клик не потратит тикет дважды (правило 1).

**Анти-эксплойт (перенесён из UAP):** пока тикетов не меньше капа, таймер регена
"замораживается" на сейчас. Иначе игрок, долго сидящий на полном хранилище, при первой
трате получил бы мгновенный "рывок" регена за всё время простоя.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_SPEND_SQL = text(
    """
    WITH cur AS (
        SELECT id, tickets_count, tickets_updated_at,
               FLOOR(EXTRACT(EPOCH FROM (now() - tickets_updated_at)) / :interval)::int AS ticks
        FROM users WHERE id = :user_id FOR UPDATE
    ), calc AS (
        SELECT id,
               CASE WHEN tickets_count >= :cap THEN tickets_count
                    ELSE LEAST(:cap, tickets_count + ticks) END AS regen_count,
               CASE WHEN tickets_count >= :cap OR tickets_count + ticks >= :cap THEN now()
                    ELSE tickets_updated_at + make_interval(secs => ticks * :interval) END AS regen_at
        FROM cur
    )
    UPDATE users u
    SET tickets_count = calc.regen_count - :amount,
        tickets_updated_at = calc.regen_at
    FROM calc
    WHERE u.id = calc.id AND calc.regen_count >= :amount
    RETURNING u.tickets_count, u.tickets_updated_at
    """
)


async def spend(
    session: AsyncSession, user_id: int, *, amount: int, cap: int, interval_seconds: int
) -> tuple[int, datetime] | None:
    """Реген + списание `amount` одним запросом. None — не хватает тикетов (строка не
    изменена). НЕ коммитит (правило 10 — часть крутки)."""
    row = (
        await session.execute(
            _SPEND_SQL, {"user_id": user_id, "amount": amount, "cap": cap, "interval": interval_seconds}
        )
    ).one_or_none()
    return (row[0], row[1]) if row else None


async def refund(session: AsyncSession, user_id: int, amount: int = 1) -> int:
    """Вернуть тикеты (бесплатная крутка от систем развития) — без регена и без потолка: это
    возврат только что списанного. НЕ коммитит. → новый баланс."""
    return await session.scalar(
        text("UPDATE users SET tickets_count = tickets_count + :amount WHERE id = :user_id RETURNING tickets_count"),
        {"user_id": user_id, "amount": amount},
    )


async def get_raw(session: AsyncSession, user_id: int) -> tuple[int, datetime] | None:
    row = (
        await session.execute(
            text("SELECT tickets_count, tickets_updated_at FROM users WHERE id = :user_id"), {"user_id": user_id}
        )
    ).one_or_none()
    return (row[0], row[1]) if row else None
