"""API-роутер Mini App: Battle Pass. Логика — только `bot.services.battle_pass` (как у бота)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.deps import get_redis
from bot.config.battle_pass import BP_LEVEL_XP, loop_position
from bot.constant.battle_pass import TRACKS
from bot.services.admin.live_config import get as live_get
from bot.services.battle_pass import (
    AlreadyPremiumError,
    BattlePassBusyError,
    LevelAlreadyClaimedError,
    LevelLockedError,
    NotEnoughDonateError,
    NothingToClaimError,
    NotPremiumError,
    buy_premium,
    claim_all,
    claim_level,
    get_page,
)
from bot.services.gang import get_gang
from bot.texts.battle_pass import (
    ALREADY_ALERT,
    BUSY_ALERT,
    LOCKED_ALERT,
    NOTHING_ALERT,
    NOT_PREMIUM_ALERT,
    PREMIUM_ALREADY_ALERT,
    PREMIUM_BOUGHT_ALERT,
    PREMIUM_NOT_ENOUGH_ALERT,
    reward_text,
)

router = APIRouter(prefix="/api/battle-pass", tags=["battle-pass"])

_NOT_ONBOARDED = "Сначала создайте банду в боте (/start)."
_ERRORS = {
    LevelLockedError: LOCKED_ALERT,
    LevelAlreadyClaimedError: ALREADY_ALERT,
    NotPremiumError: NOT_PREMIUM_ALERT,
    NothingToClaimError: NOTHING_ALERT,
    BattlePassBusyError: BUSY_ALERT,
}


class RewardItem(BaseModel):
    code: str
    amount: int


class EntryOut(BaseModel):
    level: int
    free: list[RewardItem]
    premium: list[RewardItem]
    free_claimed: bool
    premium_claimed: bool


class BoostOut(BaseModel):
    multiplier: int
    used: int
    cap: int
    resets_in: int


class PassOut(BaseModel):
    season_number: int
    season_left: int
    level: int
    xp_in_level: int
    level_xp: int
    loop_position: int
    is_premium: bool
    premium_price: int
    claimed_free: int
    claimed_premium: int
    free_claimable: bool
    premium_claimable: bool
    page: int
    pages_max: int
    boost: BoostOut
    scrolls: int
    entries: list[EntryOut]


class ClaimIn(BaseModel):
    track: str
    level: int


class ClaimAllIn(BaseModel):
    track: str


def _items(reward: dict[str, int]) -> list[RewardItem]:
    return [RewardItem(code=c, amount=a) for c, a in reward.items()]


async def _guard(session: AsyncSession, user_id: int) -> None:
    if await get_gang(session, user_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _NOT_ONBOARDED)


@router.get("", response_model=PassOut)
async def get_pass(
    page: int | None = None,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> PassOut:
    await _guard(session, user_id)
    p = await get_page(session, user_id, page)
    await session.commit()  # сезон мог открыться только что (ленивое создание)
    return PassOut(
        season_number=p.season_number, season_left=p.season_left, level=p.level, xp_in_level=p.xp_in_level,
        level_xp=BP_LEVEL_XP, loop_position=loop_position(p.level), is_premium=p.is_premium,
        premium_price=live_get("bp_premium_price"), claimed_free=p.claimed_free, claimed_premium=p.claimed_premium,
        free_claimable=p.unclaimed("free"), premium_claimable=p.unclaimed("premium"),
        page=p.page, pages_max=p.pages_max,
        boost=BoostOut(multiplier=p.boost.multiplier, used=p.boost.used, cap=p.boost.cap, resets_in=p.boost.resets_in),
        scrolls=p.scrolls,
        entries=[
            EntryOut(
                level=e.level, free=_items(e.free), premium=_items(e.premium),
                free_claimed=e.free_claimed, premium_claimed=e.premium_claimed,
            )
            for e in p.entries
        ],
    )


@router.post("/claim")
async def post_claim(
    body: ClaimIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    await _guard(session, user_id)
    if body.track not in TRACKS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, NOTHING_ALERT)
    try:
        result = await claim_level(session, redis, user_id, body.track, body.level)
    except tuple(_ERRORS) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, _ERRORS[type(exc)])
    return {"message": f"Получено: {reward_text(result.reward)}"}


@router.post("/claim-all")
async def post_claim_all(
    body: ClaimAllIn,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    await _guard(session, user_id)
    try:
        result = await claim_all(session, redis, user_id, body.track)
    except tuple(_ERRORS) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, _ERRORS[type(exc)])
    return {"message": f"Забрано уровней: {result.count}. {reward_text(result.reward)}"}


@router.post("/buy-premium")
async def post_buy_premium(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    await _guard(session, user_id)
    try:
        await buy_premium(session, redis, user_id)
    except BattlePassBusyError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, BUSY_ALERT)
    except AlreadyPremiumError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, PREMIUM_ALREADY_ALERT)
    except NotEnoughDonateError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, PREMIUM_NOT_ENOUGH_ALERT.format(price=exc.price, balance=exc.balance)
        )
    return {"message": PREMIUM_BOUGHT_ALERT}
