"""/start — вход в игру (сервис).

Онбординг страны/города (raw-notes «Карта»: «Когда игрок начинает игру он выбирает
страну... Далее он попадает на карту страны где показаны все города данной страны»).
Выбор страны — чисто презентационный шаг (переключает, какой список городов показать),
в БД ничего не пишет; страна и город фиксируются ОДНИМ шагом только когда игрок нажал на
конкретный город — страна при этом берётся из самой записи города (`City.country_code`),
а не передаётся отдельно: callback_data кнопки города несёт только `city_id`, второй
источник правды под него заводить незачем. Остальной флоу первого сообщения (banda-имя,
профиль и т.д.) — TODO, ждёт доменов `gang`/`profile`/`map` (см. CLAUDE.md, "Открытые
вопросы дизайна").
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.country import CountryDef
from bot.db.models.city import City
from bot.db.models.user import User
from bot.db.repositories.user import set_country_and_city
from bot.services.city import get_city
from bot.services.country import get_country


class UnknownCountryError(Exception):
    pass


class UnknownCityError(Exception):
    pass


def is_onboarded(user: User) -> bool:
    return user.city_id is not None


def resolve_country(code: str) -> CountryDef:
    country = get_country(code)
    if country is None:
        raise UnknownCountryError(code)
    return country


async def finish_onboarding(session: AsyncSession, user_id: int, city_id: int) -> City:
    """Завершает онбординг: проверяет, что город реально существует, затем фиксирует
    страну+город одним атомарным шагом (см. `set_country_and_city`). Если игрок уже
    прошёл онбординг раньше (гонка двух завершений подряд) — обновление молча не
    применяется, вызывающий хендлер сам решает, что показать (см. `handlers/start`)."""
    city = await get_city(session, city_id)
    if city is None:
        raise UnknownCityError(city_id)
    await set_country_and_city(session, user_id, city.country_code, city_id)
    return city
