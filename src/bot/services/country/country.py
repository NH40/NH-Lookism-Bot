"""Страны — 7 стран (Россия/США/Китай/Япония/Корея/Мексика/Казахстан) (сервис).

Список стран полностью статичен (`config/country.COUNTRIES`) — чтение НЕ ходит в БД
(правило 3, минимизация запросов доведена до предела: незачем запрашивать то, что и так
целиком лежит в памяти процесса). БД-таблица `countries` (см. `db/repositories/country`)
существует только как FK-цель для `User.country_code`/`City.country_code`, не как источник
списка для UI.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.country import COUNTRIES, COUNTRY_BY_CODE, CountryDef
from bot.db.models.country import Country
from bot.db.models.user import User
from bot.db.repositories.country import seed_countries


class BattlesClosedError(Exception):
    """В стране запрещены бои (админка). Ловится один раз на всё приложение: бот — `handlers/country`,
    API — `api/main.py`. Поэтому каждому месту боя не нужна своя ветка обработки."""

    def __init__(self, country_name: str) -> None:
        super().__init__(country_name)
        self.country_name = country_name


class CountryEntryClosedError(Exception):
    """Страна закрыта для входа (админка)."""


async def closed_entries(session: AsyncSession) -> frozenset[str]:
    """Коды стран, которые нельзя выбрать."""
    return frozenset((await session.scalars(select(Country.code).where(Country.entry_closed.is_(True)))).all())


async def ensure_entry_open(session: AsyncSession, code: str) -> None:
    if await session.scalar(select(Country.entry_closed).where(Country.code == code)):
        raise CountryEntryClosedError(code)


async def ensure_battles_open(session: AsyncSession, code: str | None) -> None:
    """Бросает `BattlesClosedError`, если в стране запрещены бои. Вызывать ДО КД и любых списаний."""
    if code and await session.scalar(select(Country.battles_closed).where(Country.code == code)):
        country = COUNTRY_BY_CODE.get(code)
        raise BattlesClosedError(country.name if country else code)


async def ensure_battles_open_for(session: AsyncSession, *user_ids: int) -> None:
    """То же по игрокам: страна берётся из их строк (войны императоров, трон)."""
    for code in (await session.scalars(select(User.country_code).where(User.id.in_(user_ids)))).all():
        await ensure_battles_open(session, code)


def list_countries() -> tuple[CountryDef, ...]:
    return COUNTRIES


def get_country(code: str) -> CountryDef | None:
    return COUNTRY_BY_CODE.get(code)


async def seed(session: AsyncSession) -> None:
    """Бутстрап `countries` — вызывается вручную через `python manager.py seed` (см.
    manager.py), ДО `services.city.seed` (тот ссылается на `countries.code` через FK)."""
    await seed_countries(session)
