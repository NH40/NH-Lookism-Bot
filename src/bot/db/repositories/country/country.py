"""Страны — 7 стран (Россия/США/Китай/Япония/Корея/Мексика/Казахстан) (репозиторий).

Список стран — не игровая механика, а фиксированный статичный контент
(`config/country.COUNTRIES`), поэтому здесь нет ничего сложнее сида и чтения — сама
логика выбора страны игроком живёт в `services/start`.
"""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.country import COUNTRIES
from bot.db.models.country import Country


async def seed_countries(session: AsyncSession) -> None:
    """Идемпотентный сид из `config/country.COUNTRIES` — `ON CONFLICT DO NOTHING` по PK
    (`code`), безопасно перезапускать сколько угодно раз (тот же приём, что
    `seed_cards.py` в Universe Anime Planet). Коммитит сама — лист-операция (правило 10),
    вызывается вручную через `python manager.py seed` (не при каждом старте бота — сид
    не игровая механика с состоянием, ему не место в горячем пути автозапуска), не
    композируется с другими шагами.
    """
    if not COUNTRIES:
        return
    stmt = (
        pg_insert(Country)
        .values([{"code": c.code, "name": c.name} for c in COUNTRIES])
        .on_conflict_do_nothing(index_elements=[Country.code])
    )
    await session.execute(stmt)
    await session.commit()


async def list_all(session: AsyncSession) -> Sequence[Country]:
    return (await session.scalars(select(Country).order_by(Country.name))).all()


async def get_by_code(session: AsyncSession, code: str) -> Country | None:
    return await session.get(Country, code)
