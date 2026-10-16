"""Промокод в Mini App — та же активация, что /promo в боте (`services/promo.redeem`)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.routers._common import bad, clean_label, require_user
from bot.handlers.promo.promo import _ERRORS, _reward_text
from bot.services import promo as promo_service
from bot.texts.promo import NOT_FOUND, REDEEMED

router = APIRouter(prefix="/api/promo", tags=["promo"])


class PromoIn(BaseModel):
    code: str


class MessageOut(BaseModel):
    message: str


@router.post("", response_model=MessageOut)
async def post_promo(body: PromoIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> MessageOut:
    user = await require_user(session, user_id, need_city=False)
    try:
        reward = await promo_service.redeem(session, user, body.code.strip())
    except promo_service.PromoError as exc:
        raise bad(clean_label(_ERRORS.get(type(exc), NOT_FOUND)))
    return MessageOut(message=clean_label(REDEEMED.format(reward=_reward_text(reward))))
