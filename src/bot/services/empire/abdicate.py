"""Сложить империю (предложение игрока Homka, решение пользователя 2026-11-12).

Императора, которого душат сильные соседи, раньше ждала только потеря городов в войнах. Теперь
при < `EMPIRE_ABDICATE_MAX_CITIES` городах он может отречься: все его города уходят ботам
(налог больше никто не платит), районы и здания во владениях сгорают, он становится кругом и
переезжает в выбранную страну своей лиги — в её самый тихий город (меньше всего жителей).
Прокачка сохраняется, штраф — `EMPIRE_ABDICATE_FINE_PERCENT`% NHCoin, перезарядка
`EMPIRE_ABDICATE_COOLDOWN_DAYS` дней (не прыгать по странам). Пока висит война — нельзя (как с
вызовом при переезде). Активные ивенты закрываются фоновым проходом с возвратом остатка.
"""
from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from bot.cache.keys import empire_abdicate_cooldown
from bot.config.country import COUNTRY_BY_CODE, countries_of
from bot.config.empire import EMPIRE_ABDICATE_COOLDOWN_DAYS, EMPIRE_ABDICATE_FINE_PERCENT, EMPIRE_ABDICATE_MAX_CITIES
from bot.constant.ledger import REASON_EMPIRE_EVENT
from bot.constant.phase import PHASE_CIRCLE, PHASE_FIST
from bot.db.models.city import City
from bot.db.repositories.travel import travel as travel_repo
from bot.services.business import accrue_many
from bot.utils.log_context import coin_reason


class NotEmperorError(Exception):
    pass


class TooManyCitiesError(Exception):
    def __init__(self, cities: int) -> None:
        super().__init__(cities)
        self.cities = cities


class AbdicateCooldownError(Exception):
    def __init__(self, seconds: int) -> None:
        super().__init__(seconds)
        self.seconds = seconds


class AtWarError(Exception):
    """Висит война императоров — сначала её итог."""


class BadCountryError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class AbdicateView:
    cities: int
    allowed: bool
    cooldown_seconds: int
    fine: int
    countries: list[tuple[str, str]]  # (код, название) — куда можно уехать


@dataclass(frozen=True, slots=True)
class Abdicated:
    country_code: str
    country_name: str
    city_name: str
    fine: int
    cities_lost: int


async def _cities(session: AsyncSession, user_id: int) -> int:
    return int(await session.scalar(text("SELECT count(*) FROM cities WHERE emperor_id = :u"), {"u": user_id}) or 0)


async def _targets(session: AsyncSession, league: int, current: str) -> list[tuple[str, str]]:
    from bot.services.country import closed_entries

    closed = await closed_entries(session)
    return [(c.code, c.name) for c in countries_of(league) if c.code != current and c.code not in closed]


async def get_view(session: AsyncSession, redis: Redis, user) -> AbdicateView:
    cities = await _cities(session, user.id)
    return AbdicateView(
        cities=cities,
        allowed=user.phase == PHASE_FIST and 0 < cities < EMPIRE_ABDICATE_MAX_CITIES,
        cooldown_seconds=max(0, await redis.ttl(empire_abdicate_cooldown(user.id))),
        fine=user.nh_coins * EMPIRE_ABDICATE_FINE_PERCENT // 100,
        countries=await _targets(session, user.league, user.country_code),
    )


async def abdicate(session: AsyncSession, redis: Redis, user_id: int, country_code: str) -> Abdicated:
    """Отречься и уехать. КД — `SET NX` (он же защита от двойного клика), при сбое снимается. Коммитит."""
    user = await travel_repo.lock_user(session, user_id)
    if user is None or user.phase != PHASE_FIST:
        raise NotEmperorError
    cities = await _cities(session, user_id)
    if not 0 < cities < EMPIRE_ABDICATE_MAX_CITIES:
        raise TooManyCitiesError(cities)
    if country_code not in dict(await _targets(session, user.league, user.country_code)):
        raise BadCountryError
    if await session.scalar(text(
        "SELECT EXISTS(SELECT 1 FROM emperor_wars WHERE status = 'pending' AND (attacker_id = :u OR defender_id = :u))"
    ), {"u": user_id}):
        raise AtWarError
    if await travel_repo.has_incoming_challenge(session, user_id):
        raise AtWarError
    key = empire_abdicate_cooldown(user_id)
    if not await redis.set(key, "1", nx=True, ex=EMPIRE_ABDICATE_COOLDOWN_DAYS * 86400):
        raise AbdicateCooldownError(max(0, await redis.ttl(key)))
    try:
        # Доход до этой секунды — по старым зданиям, потом всё сгорает.
        await accrue_many(session, [user_id])
        fine = int(await session.scalar(text("SELECT nh_coins FROM users WHERE id = :u"), {"u": user_id}) or 0)
        fine = fine * EMPIRE_ABDICATE_FINE_PERCENT // 100
        if fine:
            with coin_reason(REASON_EMPIRE_EVENT):
                await session.execute(text("UPDATE users SET nh_coins = nh_coins - :f WHERE id = :u"), {"f": fine, "u": user_id})
        await session.execute(text("UPDATE cities SET emperor_id = NULL WHERE emperor_id = :u"), {"u": user_id})
        await session.execute(text("DELETE FROM emperor_tax_overrides WHERE emperor_id = :u"), {"u": user_id})
        await session.execute(text("DELETE FROM businesses WHERE holder_id = :u"), {"u": user_id})
        await travel_repo.cancel_challenges(session, user_id)
        await travel_repo.abandon_all(session, user_id)
        await travel_repo.drop_tax_overrides(session, user_id)
        # Ивенты закрывает фоновый проход (остаток фонда — обратно уже кругу).
        await session.execute(text(
            "UPDATE empire_events SET ends_at = now() WHERE emperor_id = :u AND status = 'active'"
        ), {"u": user_id})
        city = await session.scalar(
            select(City).where(City.country_code == country_code).order_by(
                text("(SELECT count(*) FROM users r WHERE r.city_id = cities.id)"), City.id
            ).limit(1)
        )
        if city is None:
            raise BadCountryError
        await travel_repo.set_location(session, user_id, country_code, city.id, PHASE_CIRCLE)
        await session.commit()
    except Exception:
        await session.rollback()
        await redis.delete(key)
        raise
    return Abdicated(country_code, COUNTRY_BY_CODE[country_code].name, city.name, fine, cities)
