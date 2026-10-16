"""API-роутер Mini App для домена business: кошелёк (доход, накопленное, здания) и сбор.

Бизнес-логика — ТОЛЬКО через bot.services.business (тот же сервис, что вызывает и
bot.handlers.business). Строить/улучшать здания в Mini App пока нельзя — это в боте.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.deps import get_redis
from api.routers._common import bad
from api.routers.profile import plain
from bot.cache.keys import action_lock
from bot.config.game import ACTION_LOCK_MS, BUSINESS_MAX_UPGRADE
from bot.constant.business import BUSINESS_TYPES, LOCK_ACTION_BUSINESS, UPGRADE_CAPACITY, UPGRADE_LEVEL
from bot.services.business import (
    MaxUpgradeError,
    NoFreeSlotError,
    NotDistrictOwnerError,
    NotEnoughCoinsError,
    NothingToDemolishError,
    UnknownBusinessTypeError,
    build,
    build_all,
    collect,
    demolish,
    get_districts_catalog,
    get_overview,
    upgrade,
)
from bot.texts.business import (
    BUILT,
    BUILT_ALL,
    BUSINESS_DESCRIPTIONS,
    BUSINESS_NAMES,
    BUSY,
    COLLECTED,
    DEMOLISHED,
    MAX_UPGRADE,
    NO_FREE_SLOT,
    NOT_DISTRICT_OWNER,
    NOT_ENOUGH_COINS,
    NOTHING_TO_COLLECT,
    NOTHING_TO_DEMOLISH,
    NO_FREE_SLOTS_ANYWHERE,
    UPGRADE_COLLECTED,
    UPGRADED_CAPACITY,
    UPGRADED_LEVEL,
)
from bot.utils.formatting import format_number

router = APIRouter(prefix="/api/business", tags=["business"])


class BuildingOut(BaseModel):
    code: str
    name: str
    count: int


class DistrictOut(BaseModel):
    id: int
    city: str
    number: int
    used: int
    capacity: int
    free: int
    buildings: list[BuildingOut]


class CatalogItemOut(BaseModel):
    code: str
    name: str
    description: str
    cost: int
    free_first: bool  # первое кафе бесплатно (защита от софтлока)


class BusinessOut(BaseModel):
    nh_coins: int
    pending: int
    per_minute: float
    storage_full_in_seconds: int
    level: int
    capacity: int
    capacity_per_district: int
    level_cost: int | None
    capacity_cost: int | None
    tax_percent: int | None
    districts: int
    buildings: list[BuildingOut]
    gym_bonus_percent: int
    parliament_influence: int
    max_upgrade: int
    district_list: list[DistrictOut]
    catalog: list[CatalogItemOut]


@router.get("", response_model=BusinessOut)
async def get_business(
    user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> BusinessOut:
    overview = await get_overview(session, user_id)
    if overview is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Player not registered")
    w = overview.wallet
    cat = await get_districts_catalog(session, user_id)
    cap = overview.capacity_per_district
    district_list = []
    for d in overview.districts:
        counts = cat.counts.get(d.district_id, {})
        used = sum(counts.values())
        district_list.append(
            DistrictOut(
                id=d.district_id, city=d.city_name, number=d.number, used=used, capacity=cap,
                free=max(0, cap - used),
                buildings=[
                    BuildingOut(code=c, name=plain(n), count=counts[c]) for c, n in BUSINESS_NAMES.items() if counts.get(c)
                ],
            )
        )
    return BusinessOut(
        nh_coins=w.nh_coins,
        pending=w.pending,
        per_minute=round(w.per_minute, 1),
        storage_full_in_seconds=w.storage_full_in_seconds,
        level=w.level,
        capacity=w.capacity,
        capacity_per_district=overview.capacity_per_district,
        level_cost=overview.level_cost,
        capacity_cost=overview.capacity_cost,
        tax_percent=w.tax.percent if w.tax else None,
        districts=len(overview.districts),
        buildings=[
            BuildingOut(code=code, name=plain(name), count=w.counts.get(code, 0))
            for code, name in BUSINESS_NAMES.items()
        ],
        gym_bonus_percent=overview.gym_bonus_percent,
        parliament_influence=overview.parliament_influence,
        max_upgrade=BUSINESS_MAX_UPGRADE,
        district_list=district_list,
        catalog=[
            CatalogItemOut(
                code=t, name=plain(BUSINESS_NAMES[t]), description=BUSINESS_DESCRIPTIONS[t], cost=cat.build_costs[t],
                free_first=cat.build_costs[t] == 0,
            )
            for t in BUSINESS_TYPES
        ],
    )


@router.post("/collect")
async def collect_income(
    user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> dict:
    # Без Redis-лока: повторный клик ждёт FOR UPDATE первого и зачисляет ~0 (см. сервис).
    amount = await collect(session, user_id)
    return {
        "message": COLLECTED.format(amount=format_number(amount)) if amount else NOTHING_TO_COLLECT,
        "amount": amount,
    }


class BuildIn(BaseModel):
    district_id: int
    type: str


class UpgradeIn(BaseModel):
    kind: str


async def _lock(redis: Redis, user_id: int) -> str:
    key = action_lock(user_id, LOCK_ACTION_BUSINESS)
    if not await redis.set(key, "1", nx=True, px=ACTION_LOCK_MS):
        raise bad(BUSY)
    return key


def _coins_error(exc: NotEnoughCoinsError) -> HTTPException:
    return bad(NOT_ENOUGH_COINS.format(cost=format_number(exc.cost), balance=format_number(exc.balance)))


@router.post("/build")
async def build_business(
    body: BuildIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    lock = await _lock(redis, user_id)
    try:
        result = await build(session, user_id, body.district_id, body.type)
    except UnknownBusinessTypeError:
        raise bad("Неизвестный тип здания.")
    except NotDistrictOwnerError:
        raise bad(NOT_DISTRICT_OWNER)
    except NoFreeSlotError:
        raise bad(NO_FREE_SLOT)
    except NotEnoughCoinsError as exc:
        raise _coins_error(exc)
    finally:
        await redis.delete(lock)
    return {
        "message": BUILT.format(
            name=plain(BUSINESS_NAMES[result.type]), number=result.district_number, cost=format_number(result.cost)
        ),
        "cost": result.cost,
    }


@router.post("/upgrade")
async def upgrade_business(
    body: UpgradeIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    if body.kind not in (UPGRADE_LEVEL, UPGRADE_CAPACITY):
        raise bad("Неизвестный тип улучшения.")
    lock = await _lock(redis, user_id)
    try:
        result = await upgrade(session, user_id, body.kind)
    except MaxUpgradeError:
        raise bad(MAX_UPGRADE)
    except NotEnoughCoinsError as exc:
        raise _coins_error(exc)
    finally:
        await redis.delete(lock)
    template = UPGRADED_LEVEL if body.kind == UPGRADE_LEVEL else UPGRADED_CAPACITY
    return {"message": template.format(level=result.new_level, cost=format_number(result.cost))
        + (UPGRADE_COLLECTED.format(amount=format_number(result.collected)) if result.collected else ""), "new_level": result.new_level}


class BuildAllIn(BaseModel):
    type: str
    district_id: int | None = None  # None — все районы


class DemolishIn(BaseModel):
    district_id: int
    type: str | None = None  # None — снести всё на районе


@router.post("/build-all")
async def build_all_business(
    body: BuildAllIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    lock = await _lock(redis, user_id)
    try:
        result = await build_all(session, user_id, body.type, body.district_id)
    except UnknownBusinessTypeError:
        raise bad("Неизвестный тип здания.")
    except NotDistrictOwnerError:
        raise bad(NOT_DISTRICT_OWNER)
    except NoFreeSlotError:
        raise bad(NO_FREE_SLOTS_ANYWHERE)
    except NotEnoughCoinsError as exc:
        raise _coins_error(exc)
    finally:
        await redis.delete(lock)
    return {
        "message": BUILT_ALL.format(
            name=plain(BUSINESS_NAMES[result.type]), count=result.built, districts=result.districts, cost=format_number(result.cost)
        ),
        "built": result.built,
        "cost": result.cost,
    }


@router.post("/demolish")
async def demolish_business(
    body: DemolishIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    lock = await _lock(redis, user_id)
    try:
        result = await demolish(session, user_id, body.district_id, body.type)
    except UnknownBusinessTypeError:
        raise bad("Неизвестный тип здания.")
    except NotDistrictOwnerError:
        raise bad(NOT_DISTRICT_OWNER)
    except NothingToDemolishError:
        raise bad(NOTHING_TO_DEMOLISH)
    finally:
        await redis.delete(lock)
    return {"message": DEMOLISHED.format(count=result.removed, number=result.district_number), "removed": result.removed}
