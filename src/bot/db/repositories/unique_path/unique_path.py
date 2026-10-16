"""Пути (репозиторий). Функции записи НЕ коммитят — коммитит сервис."""
from __future__ import annotations

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.development import UserPath
from bot.db.models.user import User


async def list_owned(session: AsyncSession, user_id: int) -> list[tuple[str, int]]:
    rows = await session.execute(
        select(UserPath.code, UserPath.level).where(UserPath.user_id == user_id).order_by(UserPath.obtained_at)
    )
    return [(r[0], r[1]) for r in rows.all()]


async def get_state(session: AsyncSession, user_id: int) -> tuple[int, str | None, int, str | None, dict[str, int]] | None:
    """(стадия пути, активный путь, фрагменты пути, потенциал, ранги характеристик)."""
    row = (
        await session.execute(
            select(
                User.path_stage, User.active_path, User.path_fragments, User.potential,
                User.stat_strength, User.stat_speed, User.stat_endurance, User.stat_agility,
            ).where(User.id == user_id)
        )
    ).one_or_none()
    if row is None:
        return None
    stage, active, fragments, potential, *ranks = row
    return stage, active, fragments, potential, dict(zip(("strength", "speed", "endurance", "agility"), ranks))


async def advance_stage(session: AsyncSession, user_id: int, current: int, new: int) -> bool:
    """`UPDATE ... WHERE path_stage = :текущая` (правило 1) — стадию не перепрыгнуть дважды."""
    result = await session.execute(
        update(User).where(User.id == user_id, User.path_stage == current).values(path_stage=new)
    )
    return result.rowcount > 0


async def add(session: AsyncSession, user_id: int, code: str) -> bool:
    result = await session.execute(pg_insert(UserPath).values(user_id=user_id, code=code, level=1).on_conflict_do_nothing())
    return result.rowcount > 0


async def set_active(session: AsyncSession, user_id: int, code: str) -> None:
    await session.execute(update(User).where(User.id == user_id).values(active_path=code))


async def spend_fragments(session: AsyncSession, user_id: int, amount: int) -> bool:
    result = await session.execute(
        update(User).where(User.id == user_id, User.path_fragments >= amount).values(path_fragments=User.path_fragments - amount)
    )
    return result.rowcount > 0


async def get_points(session: AsyncSession, user_id: int) -> int:
    return int(await session.scalar(select(User.path_points).where(User.id == user_id)) or 0)


async def spend_points(session: AsyncSession, user_id: int, amount: int) -> bool:
    result = await session.execute(
        update(User).where(User.id == user_id, User.path_points >= amount).values(path_points=User.path_points - amount)
    )
    return result.rowcount > 0


async def awaken(session: AsyncSession, user_id: int, from_stage: int, to_stage: int, fragments: int) -> bool:
    """Списать фрагменты и перейти на стадию «путь есть» ОДНИМ условным UPDATE — двойной
    клик не пробудит путь дважды и не спишет фрагменты без результата."""
    result = await session.execute(
        update(User)
        .where(User.id == user_id, User.path_stage == from_stage, User.path_fragments >= fragments)
        .values(path_stage=to_stage, path_fragments=User.path_fragments - fragments)
    )
    return result.rowcount > 0


# Начисление очков пути: только при пробуждённом пути и если с прошлого засчитанного события
# этого источника прошло не меньше интервала. Проверка и запись метки — в том же UPDATE.
_AWARD_SQL = text(
    """
    UPDATE users
    SET path_points = path_points + CAST(:points AS bigint),
        path_point_gates = path_point_gates || jsonb_build_object(CAST(:source AS text), CAST(:now AS bigint))
    WHERE id = :uid AND path_stage = :owned
      AND COALESCE((path_point_gates ->> CAST(:source AS text))::bigint, 0) <= CAST(:now AS bigint) - CAST(:gate AS bigint)
    RETURNING path_points
    """
)


async def award_points(
    session: AsyncSession, user_id: int, source: str, points: int, gate_seconds: int, owned_stage: int, now: int
) -> int | None:
    """→ новый баланс очков; None — не засчитано (пути нет или интервал не прошёл). НЕ коммитит."""
    return await session.scalar(
        _AWARD_SQL,
        {"uid": user_id, "source": source, "points": points, "gate": gate_seconds, "owned": owned_stage, "now": now},
    )


async def bump_level(session: AsyncSession, user_id: int, code: str, current: int) -> bool:
    result = await session.execute(
        update(UserPath)
        .where(UserPath.user_id == user_id, UserPath.code == code, UserPath.level == current)
        .values(level=current + 1)
    )
    return result.rowcount > 0


async def bump_training_reps(session: AsyncSession, user_id: int) -> None:
    """+1 тренировка на Пути тренировок (личная, статистов, школа, техника). НЕ коммитит."""
    from bot.constant.unique_path import PATH_TRAINING

    await session.execute(
        update(User).where(User.id == user_id, (User.active_path == PATH_TRAINING) | (User.active_path2 == PATH_TRAINING))
        .values(training_path_reps=User.training_path_reps + 1)
    )
