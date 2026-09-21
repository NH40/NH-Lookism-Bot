"""Города — районы внутри, владение, агрегаты для карты (сервис).

Пока — только листинг городов страны для онбординга (`services/start`). Захват районов,
владение и т.п. (raw-notes «Карта») появятся здесь, когда дойдём до домена `district`.
"""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.city import City
from bot.db.repositories.city import get, list_by_country, seed_cities


async def list_cities(session: AsyncSession, country_code: str) -> Sequence[City]:
    return await list_by_country(session, country_code)


async def get_city(session: AsyncSession, city_id: int) -> City | None:
    return await get(session, city_id)


async def seed(session: AsyncSession) -> None:
    """Бутстрап `cities` — вызывается вручную через `python manager.py seed`, ПОСЛЕ
    `services.country.seed` (FK на `countries.code`)."""
    await seed_cities(session)
