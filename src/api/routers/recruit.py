"""API-роутер Mini App: вербовка статистов (`services.recruit.recruit_extra`, КД в Redis)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.deps import get_redis
from api.routers._common import bad, cooldown_text, require_user
from bot.services.recruit import RecruitOnCooldownError, recruit_extra

router = APIRouter(prefix="/api/recruit", tags=["recruit"])


class RecruitOut(BaseModel):
    message: str
    rank: str
    power: int


@router.post("/extra", response_model=RecruitOut)
async def recruit(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> RecruitOut:
    user = await require_user(session, user_id, need_city=False)
    try:
        result = await recruit_extra(session, redis, user.id, user.phase)
    except RecruitOnCooldownError as exc:
        raise bad(cooldown_text("Вербовка", exc.retry_after_seconds))
    return RecruitOut(
        message=f"Завербован статист ранга {result.rank} (мощь {result.power:,})".replace(",", " "),
        rank=result.rank, power=result.power,
    )
