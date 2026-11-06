"""Переезд между городами и странами (пользователь 2026-11-06).

Правила (ответы пользователя на AskUserQuestion того же дня):
- банда без районов — между городами своей страны свободно, смена страны — раз в
  `KEY_CD_COUNTRY_SWAP` (по умолчанию час, меняется в админке);
- банда с районами — переехать нельзя, пока не откажется от районов: районы уходят ботам,
  здания на них сгорают;
- круг — между городами своей страны свободно, всё остаётся; смена страны — с тем же КД,
  все районы и здания теряются, круг становится бандой;
- император не покидает страну, пока на троне; между её городами — свободно.
Закрытая в админке для входа страна недоступна и для переезда.
"""
from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.cache.keys import country_swap_cooldown
from bot.constant.admin.live_config import KEY_CD_COUNTRY_SWAP
from bot.constant.phase import PHASE_CIRCLE, PHASE_GANG
from bot.db.models.city import City
from bot.db.repositories import travel as repo
from bot.db.repositories.travel import Holdings
from bot.services.admin.live_config import cooldown_seconds
from bot.services.business import accrue_many
from bot.services.city import get_city
from bot.services.country import ensure_entry_open
from bot.services.phase import is_emperor


class NotOnboardedError(Exception):
    pass


class UnknownCityError(Exception):
    pass


class SameCityError(Exception):
    pass


class HasDistrictsError(Exception):
    """Банда с районами: сначала отказаться от них."""


class NoDistrictsError(Exception):
    pass


class EmperorCannotLeaveError(Exception):
    pass


class LossesNotConfirmedError(Exception):
    """Круг уезжает из страны без подтверждения потерь."""


class CountrySwapCooldownError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(retry_after_seconds)
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True, slots=True)
class TravelStatus:
    phase: str
    country_code: str
    city_id: int
    holdings: Holdings
    cooldown_seconds: int  # до смены страны
    interval_seconds: int  # КД смены страны из настроек

    @property
    def emperor(self) -> bool:
        return is_emperor(self.phase)

    @property
    def must_abandon(self) -> bool:
        """Банда с районами — никуда, пока не откажется."""
        return self.phase == PHASE_GANG and self.holdings.districts > 0


@dataclass(frozen=True, slots=True)
class MoveResult:
    city: City
    country_changed: bool
    lost: Holdings | None  # круг, сменивший страну
    became_gang: bool


async def get_status(session: AsyncSession, redis: Redis, user_id: int) -> TravelStatus:
    from bot.db.repositories.user import get_by_id

    user = await get_by_id(session, user_id)
    if user is None or user.city_id is None:
        raise NotOnboardedError
    return TravelStatus(
        phase=user.phase, country_code=user.country_code, city_id=user.city_id,
        holdings=await repo.holdings(session, user_id),
        cooldown_seconds=max(0, await redis.ttl(country_swap_cooldown(user_id))),
        interval_seconds=cooldown_seconds(KEY_CD_COUNTRY_SWAP),
    )


async def abandon_districts(session: AsyncSession, user_id: int) -> Holdings:
    """Отказаться от всех районов (банда перед переездом). Доход по старым зданиям начисляется
    до этой секунды. Коммитит. → что потеряно."""
    user = await repo.lock_user(session, user_id)
    if user is None or user.city_id is None:
        raise NotOnboardedError
    lost = await repo.holdings(session, user_id)
    if not lost.districts:
        raise NoDistrictsError
    await accrue_many(session, [user_id])
    await repo.cancel_challenges(session, user_id)
    await repo.abandon_all(session, user_id)
    await session.commit()
    return lost


async def check_move(session: AsyncSession, redis: Redis, status: TravelStatus, city: City) -> None:
    """Можно ли переехать (без записи). Подтверждение потерь круга не проверяет."""
    if city.id == status.city_id:
        raise SameCityError
    if status.must_abandon:
        raise HasDistrictsError
    if city.country_code == status.country_code:
        return
    if status.emperor:
        raise EmperorCannotLeaveError
    await ensure_entry_open(session, city.country_code)
    if status.cooldown_seconds:
        raise CountrySwapCooldownError(status.cooldown_seconds)


async def move(
    session: AsyncSession, redis: Redis, user_id: int, city_id: int, *, accept_losses: bool = False
) -> MoveResult:
    """Переехать в город. Смена страны занимает КД (`SET NX` — заодно защита от двойного
    клика), при сбое КД снимается. Коммитит."""
    city = await get_city(session, city_id)
    if city is None:
        raise UnknownCityError
    user = await repo.lock_user(session, user_id)
    if user is None or user.city_id is None:
        raise NotOnboardedError
    status = TravelStatus(
        phase=user.phase, country_code=user.country_code, city_id=user.city_id,
        holdings=await repo.holdings(session, user_id),
        cooldown_seconds=max(0, await redis.ttl(country_swap_cooldown(user_id))),
        interval_seconds=cooldown_seconds(KEY_CD_COUNTRY_SWAP),
    )
    await check_move(session, redis, status, city)
    if city.country_code == status.country_code:
        await repo.set_location(session, user_id, city.country_code, city.id)
        await session.commit()
        return MoveResult(city=city, country_changed=False, lost=None, became_gang=False)

    circle = status.phase == PHASE_CIRCLE
    if circle and status.holdings.districts and not accept_losses:
        raise LossesNotConfirmedError
    key = country_swap_cooldown(user_id)
    if not await redis.set(key, "1", nx=True, ex=max(1, status.interval_seconds)):
        raise CountrySwapCooldownError(max(0, await redis.ttl(key)))
    try:
        await repo.cancel_challenges(session, user_id)
        if status.holdings.districts:
            await accrue_many(session, [user_id])
            await repo.abandon_all(session, user_id)
        await repo.drop_tax_overrides(session, user_id)
        await repo.set_location(session, user_id, city.country_code, city.id, PHASE_GANG if circle else None)
        await session.commit()
    except Exception:
        await session.rollback()
        await redis.delete(key)
        raise
    return MoveResult(
        city=city, country_changed=True,
        lost=status.holdings if status.holdings.districts else None, became_gang=circle,
    )
