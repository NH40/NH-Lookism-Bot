"""API-роутер Mini App: рейды — текущий рейд и «встретить лагерем атаки» (`services/raid`)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.routers._common import bad, clean_label, require_user
from bot.config.raid import RAID_DIFFICULTIES
from bot.handlers.raid import outcome_text
from bot.services import raid as svc
from bot.texts.raid import DIFFICULTY_NAMES, NO_RAID

router = APIRouter(prefix="/api/raid", tags=["raid"])


@router.get("")
async def get_raid(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await require_user(session, user_id)
    r = await svc.pending_of(session, user_id)
    if r is None:
        return {"pending": None}
    left = max(0, int((r.starts_at - datetime.now(timezone.utc)).total_seconds()))
    return {"pending": {"difficulty": DIFFICULTY_NAMES[r.difficulty], "power": r.power, "starts_in": left, "lose": RAID_DIFFICULTIES[r.difficulty][2]}}


@router.post("/fight")
async def post_fight(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await require_user(session, user_id)
    try:
        outcome = await svc.fight(session, user_id)
    except svc.RaidError:
        raise bad(NO_RAID)
    return {"message": clean_label(outcome_text(outcome)), "won": outcome.won}
