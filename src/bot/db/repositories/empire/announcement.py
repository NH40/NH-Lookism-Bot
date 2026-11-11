"""Объявления императора (репозиторий). Запись не коммитит — коммитит сервис."""
from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.city import City
from bot.db.models.emperor_announcement import EmperorAnnouncement
from bot.db.models.user import User


async def emperor_city_ids(session: AsyncSession, emperor_id: int) -> list[int]:
    return list((await session.execute(select(City.id).where(City.emperor_id == emperor_id))).scalars())


async def list_subjects(session: AsyncSession, emperor_id: int, category: str) -> list[tuple[int, bool]]:
    """(игрок, выключил ли объявления) — все, кто платит налог этому императору, одним запросом."""
    rows = await session.execute(
        select(User.id, User.notify_muted.any(category))
        .join(City, City.id == User.city_id)
        .where(
            City.emperor_id == emperor_id, User.id != emperor_id,
            # Императоры, живущие в его городе, — не подданные (2026-11-12).
            ~select(City.__table__.c.id).where(City.__table__.c.emperor_id == User.id).correlate(User).exists(),
        )
    )
    return [(user_id, bool(muted)) for user_id, muted in rows.all()]


async def create(
    session: AsyncSession, *, emperor_id: int, emperor_name: str, text: str, city_ids: list[int], recipients: int, muted: int
) -> EmperorAnnouncement:
    row = EmperorAnnouncement(
        emperor_id=emperor_id, emperor_name=emperor_name, text=text, city_ids=city_ids, recipients=recipients, muted=muted
    )
    session.add(row)
    await session.flush()
    return row


async def add_delivered(session: AsyncSession, announcement_id: int, count: int) -> None:
    await session.execute(
        update(EmperorAnnouncement)
        .where(EmperorAnnouncement.id == announcement_id)
        .values(delivered=EmperorAnnouncement.delivered + count)
    )


async def list_sent(session: AsyncSession, emperor_id: int, limit: int) -> list[EmperorAnnouncement]:
    """Последние объявления императора — для его экрана со статистикой."""
    rows = await session.execute(
        select(EmperorAnnouncement)
        .where(EmperorAnnouncement.emperor_id == emperor_id)
        .order_by(EmperorAnnouncement.id.desc())
        .limit(limit)
    )
    return list(rows.scalars())


async def list_for_city(session: AsyncSession, city_id: int, offset: int, limit: int) -> list[EmperorAnnouncement]:
    """Журнал игрока: объявления, которые рассылались на его город. Берёт `limit` строк."""
    rows = await session.execute(
        select(EmperorAnnouncement)
        .where(EmperorAnnouncement.city_ids.contains([city_id]))
        .order_by(EmperorAnnouncement.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(rows.scalars())
