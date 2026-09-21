"""Экран «Профиль» — статистика, характеристики, мастерство, выбор уникальной техники/пути/родословной/гениальности/пробуждения, кнопка удаления банды (сервис).

Пока показывает только то, что реально существует (регистрация + страна/город/фаза +
название банды) — характеристики/мастерство/клан/мощь/влияние появятся, когда будут
реализованы соответствующие домены (см. CLAUDE.md, "Открытые вопросы дизайна" — раздел
«Профиль» в raw-notes сильно недоспецифицирован, додумывать несуществующие числа сейчас
не нужно, honest MVP лучше выдуманного).
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.country import CountryDef
from bot.db.models.city import City
from bot.db.repositories.user import get_by_id
from bot.services.city import get_city
from bot.services.country import get_country
from bot.services.gang import get_gang


@dataclass(frozen=True, slots=True)
class ProfileView:
    user_id: int
    username: str | None
    display_name: str | None
    is_onboarded: bool
    country: CountryDef | None
    city: City | None
    phase: str
    gang_name: str | None


async def get_profile(session: AsyncSession, user_id: int) -> ProfileView | None:
    user = await get_by_id(session, user_id)
    if user is None:
        return None

    country = get_country(user.country_code) if user.country_code else None
    city = await get_city(session, user.city_id) if user.city_id is not None else None
    gang = await get_gang(session, user_id)

    return ProfileView(
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        is_onboarded=user.city_id is not None,
        country=country,
        city=city,
        phase=user.phase,
        gang_name=gang.name if gang else None,
    )
