"""Уникальные техники (репозиторий). Функции записи НЕ коммитят — коммитит сервис."""
from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.development import UserTechnique
from bot.db.models.user import User


async def list_owned_full(session: AsyncSession, user_id: int) -> list[tuple[str, int, bool]]:
    """Техники игрока: код, уровень, выбрана ли для пути Бесконечной техники."""
    rows = await session.execute(
        select(UserTechnique.code, UserTechnique.level, UserTechnique.selected)
        .where(UserTechnique.user_id == user_id)
        .order_by(UserTechnique.obtained_at)
    )
    return [(r[0], r[1], r[2]) for r in rows.all()]


async def set_selected(session: AsyncSession, user_id: int, code: str, selected: bool) -> None:
    await session.execute(
        update(UserTechnique).where(UserTechnique.user_id == user_id, UserTechnique.code == code).values(selected=selected)
    )


async def list_owned(session: AsyncSession, user_id: int) -> list[tuple[str, int]]:
    rows = await session.execute(
        select(UserTechnique.code, UserTechnique.level)
        .where(UserTechnique.user_id == user_id)
        .order_by(UserTechnique.obtained_at)
    )
    return [(r[0], r[1]) for r in rows.all()]


async def get_state(session: AsyncSession, user_id: int) -> tuple[str | None, int] | None:
    """(активная техника, фрагменты УТ)."""
    row = (
        await session.execute(select(User.active_technique, User.technique_fragments).where(User.id == user_id))
    ).one_or_none()
    return (row[0], row[1]) if row else None


async def add(session: AsyncSession, user_id: int, code: str) -> bool:
    result = await session.execute(
        pg_insert(UserTechnique).values(user_id=user_id, code=code, level=1).on_conflict_do_nothing()
    )
    return result.rowcount > 0


async def set_active(session: AsyncSession, user_id: int, code: str | None) -> None:
    await session.execute(update(User).where(User.id == user_id).values(active_technique=code))


async def set_active_if_missing(session: AsyncSession, user_id: int, code: str) -> None:
    await session.execute(
        update(User).where(User.id == user_id, User.active_technique.is_(None)).values(active_technique=code)
    )


async def spend_fragments(session: AsyncSession, user_id: int, amount: int) -> bool:
    result = await session.execute(
        update(User)
        .where(User.id == user_id, User.technique_fragments >= amount)
        .values(technique_fragments=User.technique_fragments - amount)
    )
    return result.rowcount > 0


async def bump_level(session: AsyncSession, user_id: int, code: str, current: int) -> bool:
    result = await session.execute(
        update(UserTechnique)
        .where(UserTechnique.user_id == user_id, UserTechnique.code == code, UserTechnique.level == current)
        .values(level=current + 1)
    )
    return result.rowcount > 0


async def get_gauge(session: AsyncSession, user_id: int, code: str) -> float:
    return float(await session.scalar(select(UserTechnique.gauge).where(UserTechnique.user_id == user_id, UserTechnique.code == code)) or 0.0)


async def add_gauge(session: AsyncSession, user_id: int, code: str, amount: float, cap_per_level: float) -> None:
    """+к шкале техники, не выше потолка её уровня. НЕ коммитит."""
    from sqlalchemy import func

    await session.execute(
        update(UserTechnique)
        .where(UserTechnique.user_id == user_id, UserTechnique.code == code)
        .values(gauge=func.least(UserTechnique.gauge + amount, UserTechnique.level * cap_per_level))
    )


async def delete_all(session: AsyncSession, user_id: int) -> None:
    """Сброс (удаление банды): все техники и активная."""
    await session.execute(delete(UserTechnique).where(UserTechnique.user_id == user_id))
    await set_active(session, user_id, None)
