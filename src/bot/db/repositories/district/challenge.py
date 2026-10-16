"""Вызовы на районы игроков (PvP) — репозиторий. Все функции НЕ коммитят сами: и вызов,
и его разрешение — шаги составных операций `services/district/challenge.py` (правило 10)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constant.district import CHALLENGE_PENDING, CHALLENGE_RESOLVED, SCOPE_CITY, SCOPE_DISTRICT
from bot.db.models.district_challenge import DistrictChallenge


async def create(
    session: AsyncSession,
    *,
    city_id: int,
    district_id: int | None,
    attacker_id: int,
    defender_id: int,
    expires_at: datetime,
) -> int | None:
    """`district_id=None` — вызов круга за весь город (`scope='city'`). `ON CONFLICT DO
    NOTHING` без явной цели срабатывает на ЛЮБОЙ из частичных уникальных индексов (висящий
    вызов на район / за город на того же защитника / исходящий у нападающего) — `None`
    значит "вызов уже есть", гонка двух кликов решается базой (правило 1)."""
    stmt = (
        pg_insert(DistrictChallenge)
        .values(
            scope=SCOPE_DISTRICT if district_id is not None else SCOPE_CITY,
            city_id=city_id,
            district_id=district_id,
            attacker_id=attacker_id,
            defender_id=defender_id,
            expires_at=expires_at,
        )
        .on_conflict_do_nothing()
        .returning(DistrictChallenge.id)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get(session: AsyncSession, challenge_id: int) -> DistrictChallenge | None:
    return await session.get(DistrictChallenge, challenge_id)


async def get_pending_for_district(session: AsyncSession, district_id: int) -> DistrictChallenge | None:
    return await session.scalar(
        select(DistrictChallenge).where(
            DistrictChallenge.district_id == district_id, DistrictChallenge.status == CHALLENGE_PENDING
        )
    )


async def list_pending_city_defenders(session: AsyncSession, city_id: int) -> set[int]:
    """Защитники города, на которых уже висит вызов круга за город — для пометки на экране."""
    rows = await session.scalars(
        select(DistrictChallenge.defender_id).where(
            DistrictChallenge.city_id == city_id,
            DistrictChallenge.scope == SCOPE_CITY,
            DistrictChallenge.status == CHALLENGE_PENDING,
        )
    )
    return set(rows)


async def get_pending_for_attacker(session: AsyncSession, attacker_id: int) -> DistrictChallenge | None:
    return await session.scalar(
        select(DistrictChallenge).where(
            DistrictChallenge.attacker_id == attacker_id, DistrictChallenge.status == CHALLENGE_PENDING
        )
    )


async def claim(session: AsyncSession, challenge_id: int, resolution: str) -> DistrictChallenge | None:
    """Атомарно "забирает" висящий вызов на разрешение (`UPDATE ... WHERE status='pending'
    RETURNING`, правило 1) — если защитник нажал "Принять" ровно в момент, когда sweep
    подхватил просроченный вызов, бой проведёт только тот, кто забрал первым; второй
    получит `None`. Без этого один вызов мог бы разрешиться двумя боями подряд."""
    stmt = (
        update(DistrictChallenge)
        .where(DistrictChallenge.id == challenge_id, DistrictChallenge.status == CHALLENGE_PENDING)
        .values(status=CHALLENGE_RESOLVED, resolution=resolution, resolved_at=func.now())
        .returning(DistrictChallenge)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def set_outcome(session: AsyncSession, challenge_id: int, *, resolution: str, attacker_won: bool | None) -> None:
    await session.execute(
        update(DistrictChallenge)
        .where(DistrictChallenge.id == challenge_id)
        .values(resolution=resolution, attacker_won=attacker_won)
    )


async def list_expired_ids(session: AsyncSession, limit: int) -> list[int]:
    """Индекс по `expires_at` — sweep раз в минуту не сканирует таблицу целиком (правило 6)."""
    rows = await session.scalars(
        select(DistrictChallenge.id)
        .where(DistrictChallenge.status == CHALLENGE_PENDING, DistrictChallenge.expires_at <= func.now())
        .order_by(DistrictChallenge.expires_at)
        .limit(limit)
    )
    return list(rows)
