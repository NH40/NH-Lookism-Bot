"""Экран «Профиль» — статистика, характеристики, мастерство, выбор уникальной техники/пути/родословной/гениальности/пробуждения, кнопка удаления банды (репозиторий).

TODO: дизайн — см. `docs/design/lookism_battle_planet_2_raw_notes.md`, раздел: «Профиль» + конец блока «Фазы» (кнопка удаления банды). Многое там ЯВНО не доспецифицировано
(формулы/тайминги/содержание) — перед реализацией уточнять через AskUserQuestion,
не додумывать молча (см. CLAUDE.md, feedback про это).
"""


from datetime import datetime, timedelta, timezone  # noqa: E402

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from bot.db.models.city import City  # noqa: E402
from bot.db.models.district import District  # noqa: E402
from bot.db.models.user import User  # noqa: E402


async def count_online(session: AsyncSession, within_minutes: int) -> int:
    """Игроки, активные за последние `within_minutes` минут (`users.last_active_at`)."""
    since = datetime.now(timezone.utc) - timedelta(minutes=within_minutes)
    return await session.scalar(select(func.count(User.id)).where(User.last_active_at >= since)) or 0


async def count_districts_in_city(session: AsyncSession, city_id: int) -> int:
    return await session.scalar(select(func.count(District.id)).where(District.city_id == city_id)) or 0


async def count_districts_in_country(session: AsyncSession, country_code: str) -> int:
    return (
        await session.scalar(
            select(func.count(District.id)).join(City, City.id == District.city_id).where(City.country_code == country_code)
        )
        or 0
    )
