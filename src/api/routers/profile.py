"""API-роутер Mini App для домена profile.

Бизнес-логика — ТОЛЬКО через `bot.services.profile` (тот же сервис, что вызывает и
`bot.handlers.profile`) — роутер не дублирует и не переизобретает правила, только
валидирует initData и мапит результат в pydantic-схему (см. CLAUDE.md, «Mini App» —
единая точка бизнес-логики для бота и Mini App).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.schemas import CityOut, CountryOut, ProfileOut
from bot.services.profile import get_profile

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=ProfileOut)
async def get_my_profile(
    user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> ProfileOut:
    profile = await get_profile(session, user_id)
    if profile is None:
        # Mini App открыт игроком, который ни разу не нажимал /start боту — такой
        # строки в users ещё нет (тот же прецедент, что api/routers/profile.py в UAP).
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Player not registered — open the bot and press /start first"
        )

    return ProfileOut(
        user_id=profile.user_id,
        username=profile.username,
        display_name=profile.display_name,
        is_onboarded=profile.is_onboarded,
        country=CountryOut(code=profile.country.code, name=profile.country.name) if profile.country else None,
        city=CityOut(id=profile.city.id, name=profile.city.name, district_count=profile.city.district_count)
        if profile.city
        else None,
        phase=profile.phase,
        gang_name=profile.gang_name,
    )
