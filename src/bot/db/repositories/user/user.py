"""Игрок — ядро аккаунта (репозиторий).

TODO: дизайн — см. `docs/design/lookism_battle_planet_2_raw_notes.md` (характеристики,
мощь, влияние, фаза, страна, банда и т.д. — расширяется по мере переноса каждого
домена, не всё разом здесь). Многое там ЯВНО не доспецифицировано (формулы/тайминги) —
перед реализацией уточнять через AskUserQuestion, не додумывать молча.

Пока — только то, что нужно инфраструктуре (middlewares/tech_mode, services/admin).
"""
from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models.user import User


async def get_by_id(session: AsyncSession, user_id: int) -> User | None:
    return await session.scalar(select(User).where(User.id == user_id))


async def upsert_from_telegram(
    session: AsyncSession, *, user_id: int, username: str | None, display_name: str | None
) -> User:
    """Регистрация/обновление игрока при каждом /start. Атомарный upsert одним запросом
    (тот же паттерн, что в Universe Anime Planet) — без гонки "проверили что нет —
    вставили" при параллельных апдейтах от одного пользователя. На ON CONFLICT трогаем
    только username/display_name (могли поменяться в Telegram) — остальные поля
    (is_banned/is_admin) не должны сбрасываться повторным /start."""
    stmt = (
        pg_insert(User)
        .values(id=user_id, username=username, display_name=display_name)
        .on_conflict_do_update(
            index_elements=[User.id],
            set_={"username": username, "display_name": display_name},
        )
        .returning(User)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.scalar_one()


async def set_country_and_city(
    session: AsyncSession, user_id: int, country_code: str, city_id: int
) -> bool:
    """Завершение онбординга (домен `start`) — страна и город фиксируются ОДНИМ атомарным
    `UPDATE ... WHERE city_id IS NULL` (правило 1), не двумя отдельными шагами: до этого
    момента выбор страны/города — чисто презентационная навигация между сообщениями
    (см. `services/start`), в БД ничего не пишется, поэтому нет промежуточного состояния
    "страна есть, город ещё нет" — только "не играет" / "играет". `city_id IS NULL` —
    единственный и постоянный guard: онбординг проходится ровно один раз, до появления
    кнопки "сбросить банду" в профиле. `bool` в возврате — реально ли применилось
    изменение (гонка двух завершений онбординга подряд от одного игрока — второй молча
    не срабатывает)."""
    stmt = (
        update(User)
        .where(User.id == user_id, User.city_id.is_(None))
        .values(country_code=country_code, city_id=city_id)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount > 0
