"""Родословная Пеньгуана в Mini App — те же бафы, выкупы и конструктор, что в боте (`services/penguan`)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.deps import get_redis
from api.routers._common import bad, clean_label, require_user
from bot.config.penguan import PG_ATTACK_CAP, PG_BUY_PRESETS, PG_INFLUENCE_CAP, PG_LAND_INCOME_CAP, PG_WEALTH_CAP
from bot.services import penguan as svc
from bot.services.build import get_build
from bot.services.country import BattlesClosedError
from bot.texts import penguan as t
from bot.texts.school import SCHOOL_NAMES

router = APIRouter(prefix="/api/penguan", tags=["penguan"])


class BuffOut(BaseModel):
    kind: str
    name: str
    effect: str
    price: int
    active_in: int  # секунд до конца (0 — не куплен)


class PenguanOut(BaseModel):
    active: bool  # у игрока родословная Пеньгуана (первая или второго тела)
    income: int
    districts: int
    cities: int
    points: float
    points_cap: float
    bonuses: list[str]
    buffs: list[BuffOut]
    buyback: dict | None  # {units, power, price}
    buyout: dict | None  # {price, cooldown}
    builder: bool


class BuilderOut(BaseModel):
    rank: str
    ceiling: str
    level: int
    level_cap: int
    stars: int
    school: str
    school_label: str
    school_level: int
    unit_power: int
    unit_price: int
    bought_today: int
    daily_cap: int
    max_units: int
    presets: list[int]


class MessageOut(BaseModel):
    message: str


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def _n(x: int) -> str:
    return f"{x:,}".replace(",", " ")


def _bonus(line: str) -> str:
    """«⚔️ +12% к атаке…» → «+12% к атаке…»: убрать эмодзи, но оставить знак (`clean_label` срезал бы и «+»)."""
    return line.strip().split(" ", 1)[-1]


def _fail(exc: svc.PenguanError):
    return bad(clean_label(t.ERRORS[exc.code].format(*(_n(v) for v in exc.values))))


@router.get("", response_model=PenguanOut)
async def home(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
               redis: Redis = Depends(get_redis)) -> PenguanOut:
    user = await require_user(session, user_id, need_city=False)
    build = await get_build(session, user_id)
    pg = build.pg
    w = await svc.wealth(session, user_id)
    bonuses = []
    if pg.get("pg_attack"):
        bonuses.append(_bonus(t.BONUS_ATTACK.format(p=_pct(min(PG_ATTACK_CAP, pg["pg_attack"] * w.points)))))
    if pg.get("pg_influence"):
        bonuses.append(_bonus(t.BONUS_INFLUENCE.format(p=_pct(min(PG_INFLUENCE_CAP, pg["pg_influence"] * w.points)))))
    if pg.get("pg_land_income"):
        land = pg["pg_land_income"] * w.districts / 10 + pg.get("pg_city_income", 0.0) * w.cities
        bonuses.append(_bonus(t.BONUS_INCOME.format(p=_pct(min(PG_LAND_INCOME_CAP, land)))))
    now = datetime.now(timezone.utc)
    buffs = [
        BuffOut(kind=o.kind, name=clean_label(t.BUFF_NAMES[o.kind]), effect=t.BUFF_EFFECTS[o.kind].format(p=_pct(o.power)), price=o.price,
                active_in=max(0, int((o.active_until - now).total_seconds())) if o.active_until else 0)
        for o in await svc.buff_offers(session, user_id)
    ]
    back = await svc.buyback_offer(session, user_id)
    out = await svc.buyout_offer(session, redis, user)
    return PenguanOut(
        active=bool(pg), income=w.income, districts=w.districts, cities=w.cities, points=round(w.points, 2), points_cap=PG_WEALTH_CAP,
        bonuses=bonuses, buffs=buffs,
        buyback={"units": back.units, "power": back.power, "price": back.price} if back else None,
        buyout={"price": out.price, "cooldown": out.cooldown} if out else None,
        builder=bool(pg.get("pg_constructor")),
    )


class BuffIn(BaseModel):
    kind: str


@router.post("/buff", response_model=MessageOut)
async def buff(body: BuffIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
               redis: Redis = Depends(get_redis)) -> MessageOut:
    try:
        offer = await svc.buy_buff(session, redis, user_id, body.kind)
    except svc.PenguanError as exc:
        raise _fail(exc)
    return MessageOut(message=clean_label(t.BUFF_BOUGHT.format(name=t.BUFF_NAMES[offer.kind], price=_n(offer.price))))


@router.post("/buyback", response_model=MessageOut)
async def buyback(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                  redis: Redis = Depends(get_redis)) -> MessageOut:
    try:
        offer = await svc.buyback(session, redis, user_id)
    except svc.PenguanError as exc:
        raise _fail(exc)
    return MessageOut(message=clean_label(t.BUYBACK_DONE.format(units=_n(offer.units), price=_n(offer.price))))


@router.post("/buyout", response_model=MessageOut)
async def buyout(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                 redis: Redis = Depends(get_redis)) -> MessageOut:
    user = await require_user(session, user_id)
    try:
        number, price, _ = await svc.buyout(session, redis, user)
    except svc.PenguanError as exc:
        raise _fail(exc)
    except BattlesClosedError:
        raise bad(clean_label(t.ERRORS["phase"]))
    return MessageOut(message=clean_label(t.BUYOUT_DONE.format(number=number, price=_n(price))))


async def _builder(session: AsyncSession, redis: Redis, user_id: int) -> BuilderOut:
    try:
        v = await svc.builder_view(session, redis, user_id)
    except svc.PenguanError as exc:
        raise _fail(exc)
    d = v.design
    return BuilderOut(
        rank=d.rank, ceiling=v.ceiling, level=d.level, level_cap=v.level_cap, stars=d.stars, school=d.school,
        school_label=clean_label(SCHOOL_NAMES.get(d.school, d.school)) if d.school else "без школы", school_level=d.school_level,
        unit_power=int(v.unit_power), unit_price=v.unit_price, bought_today=v.bought_today, daily_cap=v.daily_cap, max_units=v.max_units,
        presets=sorted({n for n in PG_BUY_PRESETS if n <= v.max_units} | ({v.max_units} if v.max_units else set())),
    )


@router.get("/builder", response_model=BuilderOut)
async def builder(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                  redis: Redis = Depends(get_redis)) -> BuilderOut:
    await require_user(session, user_id, need_city=False)
    return await _builder(session, redis, user_id)


class SetIn(BaseModel):
    param: str
    delta: int


@router.post("/builder/set", response_model=BuilderOut)
async def builder_set(body: SetIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                      redis: Redis = Depends(get_redis)) -> BuilderOut:
    try:
        await svc.change_design(redis, session, user_id, body.param, body.delta)
    except svc.PenguanError as exc:
        raise _fail(exc)
    return await _builder(session, redis, user_id)


class BuyIn(BaseModel):
    quantity: int


@router.post("/builder/buy", response_model=MessageOut)
async def builder_buy(body: BuyIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                      redis: Redis = Depends(get_redis)) -> MessageOut:
    try:
        n, price = await svc.buy_statists(session, redis, user_id, body.quantity)
    except svc.PenguanError as exc:
        raise _fail(exc)
    return MessageOut(message=clean_label(t.BOUGHT.format(n=_n(n), price=_n(price))))
