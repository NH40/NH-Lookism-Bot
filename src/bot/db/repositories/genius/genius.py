"""Гениальности (репозиторий). Функции записи НЕ коммитят — коммитит сервис."""
from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.development import UserGenius
from bot.db.models.user import User


async def list_owned(session: AsyncSession, user_id: int) -> list[tuple[str, int]]:
    rows = await session.execute(
        select(UserGenius.code, UserGenius.level).where(UserGenius.user_id == user_id).order_by(UserGenius.obtained_at)
    )
    return [(r[0], r[1]) for r in rows.all()]


async def get_state(session: AsyncSession, user_id: int) -> tuple[str | None, int, int] | None:
    """(активная гениальность, фрагменты гениальности, NHCoin)."""
    row = (
        await session.execute(select(User.active_genius, User.genius_fragments, User.nh_coins).where(User.id == user_id))
    ).one_or_none()
    return (row[0], row[1], row[2]) if row else None


async def add(session: AsyncSession, user_id: int, code: str) -> bool:
    """Новая гениальность 1 уровня. False — уже есть (повтор прокрута)."""
    result = await session.execute(
        pg_insert(UserGenius).values(user_id=user_id, code=code, level=1).on_conflict_do_nothing()
    )
    return result.rowcount > 0


async def set_active(session: AsyncSession, user_id: int, code: str) -> None:
    await session.execute(update(User).where(User.id == user_id).values(active_genius=code))


async def set_active_if_missing(session: AsyncSession, user_id: int, code: str) -> None:
    await session.execute(
        update(User).where(User.id == user_id, User.active_genius.is_(None)).values(active_genius=code)
    )


async def spend_fragments(session: AsyncSession, user_id: int, amount: int, coins: int = 0) -> bool:
    """Атомарное списание фрагментов (и NHCoin) одним `UPDATE ... WHERE хватает` (правило 1)."""
    result = await session.execute(
        update(User)
        .where(User.id == user_id, User.genius_fragments >= amount, User.nh_coins >= coins)
        .values(genius_fragments=User.genius_fragments - amount, nh_coins=User.nh_coins - coins)
    )
    return result.rowcount > 0


async def bump_level(session: AsyncSession, user_id: int, code: str, current: int) -> bool:
    """+1 уровень, только если он всё ещё `current` (двойной клик не перепрыгнет)."""
    result = await session.execute(
        update(UserGenius)
        .where(UserGenius.user_id == user_id, UserGenius.code == code, UserGenius.level == current)
        .values(level=current + 1)
    )
    return result.rowcount > 0
