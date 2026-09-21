"""Страны — 7 стран (Россия/США/Китай/Япония/Корея/Мексика/Казахстан) (сервис).

Список стран полностью статичен (`config/country.COUNTRIES`) — чтение НЕ ходит в БД
(правило 3, минимизация запросов доведена до предела: незачем запрашивать то, что и так
целиком лежит в памяти процесса). БД-таблица `countries` (см. `db/repositories/country`)
существует только как FK-цель для `User.country_code`/`City.country_code`, не как источник
списка для UI.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.country import COUNTRIES, COUNTRY_BY_CODE, CountryDef
from bot.db.repositories.country import seed_countries


def list_countries() -> tuple[CountryDef, ...]:
    return COUNTRIES


def get_country(code: str) -> CountryDef | None:
    return COUNTRY_BY_CODE.get(code)


async def seed(session: AsyncSession) -> None:
    """Бутстрап `countries` — вызывается вручную через `python manager.py seed` (см.
    manager.py), ДО `services.city.seed` (тот ссылается на `countries.code` через FK)."""
    await seed_countries(session)
