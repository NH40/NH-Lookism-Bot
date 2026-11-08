"""Переезд между городами и странами (репозиторий). Ничего не коммитит — коммитит сервис."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.admin.world import CHALLENGE_CANCELLED
from bot.constant.district import CHALLENGE_PENDING, RESOLUTION_TRAVEL
from bot.db.models.user import User


@dataclass(frozen=True, slots=True)
class Holdings:
    districts: int
    buildings: int
    cities: int  # в скольких городах есть районы


async def lock_user(session: AsyncSession, user_id: int) -> User | None:
    """Строка игрока под `FOR UPDATE`: переезд, отказ от районов и захват не идут одновременно."""
    return await session.scalar(select(User).where(User.id == user_id).with_for_update())


async def holdings(session: AsyncSession, user_id: int) -> Holdings:
    row = (await session.execute(text("""
        SELECT count(*), count(DISTINCT d.city_id),
               (SELECT count(*) FROM businesses b JOIN districts d2 ON d2.id = b.district_id WHERE d2.owner_id = :uid)
        FROM districts d WHERE d.owner_id = :uid
    """), {"uid": user_id})).one()
    return Holdings(districts=int(row[0]), cities=int(row[1]), buildings=int(row[2]))


async def cancel_challenges(session: AsyncSession, user_id: int) -> int:
    """Висящие вызовы с участием игрока: он уходит, бой не должен дозреть."""
    result = await session.execute(text("""
        UPDATE district_challenges SET status = :cancelled, resolution = :travel, resolved_at = now()
        WHERE status = :pending AND (attacker_id = :uid OR defender_id = :uid)
    """), {"uid": user_id, "cancelled": CHALLENGE_CANCELLED, "travel": RESOLUTION_TRAVEL, "pending": CHALLENGE_PENDING})
    return result.rowcount or 0


async def has_incoming_challenge(session: AsyncSession, user_id: int) -> bool:
    return bool(await session.scalar(
        text("SELECT 1 FROM district_challenges WHERE status = :pending AND defender_id = :uid LIMIT 1"),
        {"uid": user_id, "pending": CHALLENGE_PENDING},
    ))


async def abandon_all(session: AsyncSession, user_id: int) -> None:
    """Все районы игрока — ботам, здания на них сгорают (пользователь 2026-11-06)."""
    await session.execute(
        text("DELETE FROM businesses WHERE district_id IN (SELECT id FROM districts WHERE owner_id = :uid)"),
        {"uid": user_id},
    )
    await session.execute(
        text("UPDATE districts SET owner_id = NULL, captured_at = NULL WHERE owner_id = :uid"), {"uid": user_id}
    )


async def drop_tax_overrides(session: AsyncSession, user_id: int) -> None:
    """Персональные ставки налога игроку — у нового императора их нет."""
    await session.execute(text("DELETE FROM emperor_tax_overrides WHERE user_id = :uid"), {"uid": user_id})


async def set_location(
    session: AsyncSession, user_id: int, country_code: str, city_id: int, phase: str | None = None
) -> None:
    values = {"country_code": country_code, "city_id": city_id}
    if phase is not None:
        values["phase"] = phase
    await session.execute(update(User).where(User.id == user_id).values(**values))
