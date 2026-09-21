"""Города — районы внутри, владение, агрегаты для карты (репозиторий).

Пока — только сид/чтение статичного списка городов (`config/city.CITY_SEEDS`). Владение
районами, захват и т.п. (raw-notes «Карта») — домен `district`, ещё не реализован; этот
репозиторий про сами города как сущности, не про боевое состояние внутри них.
"""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.city import CITY_SEEDS
from bot.db.models.city import City


async def seed_cities(session: AsyncSession) -> None:
    """Идемпотентный сид из `config/city.CITY_SEEDS` — `ON CONFLICT DO NOTHING` по
    уникальному `(country_code, name)`, безопасно перезапускать сколько угодно раз:
    в отличие от простого "пропустить, если таблица не пуста" (как было в
    LookismBattlePlanet 1.0, `app/main.py: init_cities`), это позволяет добавлять новые
    города в `CITY_SEEDS` в будущем и просто передеплоить, не трогая уже существующие
    строки (владение районами у них не сбросится). Коммитит сама — лист-операция
    (правило 10), вызывается вручную через `python manager.py seed` (не при каждом
    старте бота — см. CLAUDE.md). Требует, чтобы `seed_countries` уже отработал (FK на
    `countries.code`).
    """
    if not CITY_SEEDS:
        return
    stmt = (
        pg_insert(City)
        .values(
            [
                {"country_code": c.country_code, "name": c.name, "district_count": c.district_count}
                for c in CITY_SEEDS
            ]
        )
        .on_conflict_do_nothing(constraint="uq_cities_country_name")
    )
    await session.execute(stmt)
    await session.commit()


async def list_by_country(session: AsyncSession, country_code: str) -> Sequence[City]:
    return (
        await session.scalars(
            select(City)
            .where(City.country_code == country_code)
            .order_by(City.district_count.desc(), City.name)
        )
    ).all()


async def get(session: AsyncSession, city_id: int) -> City | None:
    return await session.get(City, city_id)
