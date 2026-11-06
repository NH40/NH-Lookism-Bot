"""Переезд в Mini App — те же правила и ошибки, что у бота (`services/travel`)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.deps import get_redis
from api.routers._common import bad, clean_label
from bot.config.country import COUNTRIES, COUNTRY_BY_CODE
from bot.constant.phase import PHASE_CIRCLE
from bot.handlers.travel.travel import interval_label
from bot.services.city import get_city, list_cities
from bot.services.country import CountryEntryClosedError, closed_entries
from bot.services.travel import (
    CountrySwapCooldownError,
    EmperorCannotLeaveError,
    HasDistrictsError,
    LossesNotConfirmedError,
    NoDistrictsError,
    NotOnboardedError,
    SameCityError,
    UnknownCityError,
    abandon_districts,
    get_status,
    move,
)
from bot.texts.country import COUNTRY_CLOSED_ALERT
from bot.texts.travel import (
    ABANDONED,
    COOLDOWN_ALERT,
    EMPEROR_ALERT,
    HAS_DISTRICTS_ALERT,
    MOVED,
    MOVED_LOST,
    NO_DISTRICTS_ALERT,
    NOT_ONBOARDED_ALERT,
    SAME_CITY_ALERT,
    UNKNOWN_CITY_ALERT,
)
from bot.utils.formatting import format_countdown

router = APIRouter(prefix="/api/travel", tags=["travel"])

_ERRORS = {
    NotOnboardedError: NOT_ONBOARDED_ALERT,
    SameCityError: SAME_CITY_ALERT,
    HasDistrictsError: HAS_DISTRICTS_ALERT,
    NoDistrictsError: NO_DISTRICTS_ALERT,
    EmperorCannotLeaveError: EMPEROR_ALERT,
    UnknownCityError: UNKNOWN_CITY_ALERT,
    CountryEntryClosedError: COUNTRY_CLOSED_ALERT,
    LossesNotConfirmedError: "Подтверди потерю районов.",
}


def _error(exc: Exception):
    if isinstance(exc, CountrySwapCooldownError):
        return bad(COOLDOWN_ALERT.format(countdown=format_countdown(exc.retry_after_seconds)))
    return bad(_ERRORS[type(exc)])


def _name(code: str | None) -> str:
    country = COUNTRY_BY_CODE.get(code or "")
    return clean_label(country.name) if country else (code or "—")


class CountryOut(BaseModel):
    code: str
    name: str


class TravelOut(BaseModel):
    phase: str
    country_code: str
    country: str
    city_id: int
    city: str
    districts: int
    buildings: int
    cities: int
    cooldown_seconds: int
    interval: str
    emperor: bool
    must_abandon: bool
    circle: bool
    countries: list[CountryOut]  # куда можно уехать (без своей и закрытых)


@router.get("", response_model=TravelOut)
async def get_travel(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> TravelOut:
    try:
        s = await get_status(session, redis, user_id)
    except NotOnboardedError as e:
        raise _error(e)
    city = await get_city(session, s.city_id)
    closed = set(await closed_entries(session))
    return TravelOut(
        phase=s.phase, country_code=s.country_code, country=_name(s.country_code), city_id=s.city_id,
        city=city.name if city else "—", districts=s.holdings.districts, buildings=s.holdings.buildings,
        cities=s.holdings.cities, cooldown_seconds=s.cooldown_seconds, interval=interval_label(s.interval_seconds),
        emperor=s.emperor, must_abandon=s.must_abandon, circle=s.phase == PHASE_CIRCLE,
        countries=[
            CountryOut(code=c.code, name=clean_label(c.name))
            for c in COUNTRIES
            if c.code != s.country_code and c.code not in closed
        ],
    )


class CityOut(BaseModel):
    id: int
    name: str
    districts: int


@router.get("/cities", response_model=list[CityOut])
async def get_cities(
    country: str = Query(..., min_length=2, max_length=2), session: AsyncSession = Depends(get_session)
) -> list[CityOut]:
    if country not in COUNTRY_BY_CODE:
        raise bad(UNKNOWN_CITY_ALERT)
    return [CityOut(id=c.id, name=c.name, districts=c.district_count) for c in await list_cities(session, country)]


class MessageOut(BaseModel):
    message: str


class MoveIn(BaseModel):
    city_id: int
    accept_losses: bool = False


@router.post("/move", response_model=MessageOut)
async def post_move(
    body: MoveIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> MessageOut:
    try:
        result = await move(session, redis, user_id, body.city_id, accept_losses=body.accept_losses)
    except tuple(_ERRORS) + (CountrySwapCooldownError,) as e:
        raise _error(e)
    text = MOVED.format(country=_name(result.city.country_code), city=result.city.name)
    if result.lost:
        text += MOVED_LOST.format(districts=result.lost.districts, buildings=result.lost.buildings)
    return MessageOut(message=clean_label(text))


@router.post("/abandon", response_model=MessageOut)
async def post_abandon(
    user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> MessageOut:
    try:
        lost = await abandon_districts(session, user_id)
    except tuple(_ERRORS) as e:
        raise _error(e)
    return MessageOut(message=clean_label(ABANDONED.format(districts=lost.districts, buildings=lost.buildings)))
