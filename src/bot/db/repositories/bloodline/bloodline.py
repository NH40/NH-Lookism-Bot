"""Родословная (репозиторий)."""
from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.user import User


async def get_state(session: AsyncSession, user_id: int) -> tuple[str | None, int, int] | None:
    """(родословная, уровень, капли крови) или None, если игрока нет."""
    row = (
        await session.execute(
            select(User.bloodline, User.bloodline_level, User.blood_drops).where(User.id == user_id)
        )
    ).one_or_none()
    return (row[0], row[1], row[2]) if row else None


async def choose(session: AsyncSession, user_id: int, code: str) -> bool:
    """Выбор навсегда: `UPDATE ... WHERE bloodline IS NULL` (правило 1) — двойной клик или
    вторая вкладка не перевыберут. False — уже выбрана. НЕ коммитит."""
    result = await session.execute(
        update(User).where(User.id == user_id, User.bloodline.is_(None)).values(bloodline=code)
    )
    return result.rowcount > 0


async def set_level_if_zero(session: AsyncSession, user_id: int, level: int) -> None:
    """Стартовый уровень при выборе (и починка выбравших до появления уровней). НЕ коммитит."""
    await session.execute(
        update(User).where(User.id == user_id, User.bloodline.is_not(None), User.bloodline_level < level).values(bloodline_level=level)
    )


async def level_up(session: AsyncSession, user_id: int, current: int, cost: int) -> bool:
    """+1 уровень за капли крови одним условным UPDATE (правило 1): уровень всё ещё
    `current` и капель хватает. НЕ коммитит."""
    result = await session.execute(
        update(User)
        .where(User.id == user_id, User.bloodline_level == current, User.blood_drops >= cost)
        .values(bloodline_level=current + 1, blood_drops=User.blood_drops - cost)
    )
    return result.rowcount > 0


async def raise_stats_to(session: AsyncSession, user_id: int, floor: int) -> None:
    """Пол характеристик (Ким Гапрен): каждая не ниже `floor` — одним UPDATE. НЕ коммитит."""
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(
            stat_strength=func.greatest(User.stat_strength, floor),
            stat_speed=func.greatest(User.stat_speed, floor),
            stat_endurance=func.greatest(User.stat_endurance, floor),
            stat_agility=func.greatest(User.stat_agility, floor),
        )
    )
