"""Заявки на районы после перехода в лигу (2026-11-23) — список и бесплатный вызов. Логика — `bot.services.league.move`."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.deps import get_redis
from api.routers._common import bad, require_user
from bot.services.league.move import ClaimError, open_claims, start_claim
from bot.texts.league import CLAIM_ERRORS, CLAIM_TAKEN

router = APIRouter(prefix="/api/league", tags=["league"])


@router.get("/claims")
async def get_claims(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    return {"claims": [{"id": cid, "number": n, "city": city, "expires_at": exp.isoformat(), "in_progress": busy}
                       for cid, n, city, exp, busy in await open_claims(session, user_id)]}


@router.post("/claims/{claim_id}")
async def fight_claim(claim_id: int, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                      redis: Redis = Depends(get_redis)) -> dict:
    """Бесплатный вызов по заявке (без КД). Район освободился — забран сразу."""
    user = await require_user(session, user_id)
    try:
        issued = await start_claim(session, redis, user, claim_id)
    except ClaimError as exc:
        raise bad(CLAIM_ERRORS.get(exc.code, "Не вышло."))
    except Exception as exc:  # noqa: BLE001 — гонка вызовов на район и т.п.
        from bot.handlers.district.district import attack_error_text

        text = attack_error_text(exc)
        if text is None:
            raise
        raise bad(text)
    if issued is None:
        return {"message": CLAIM_TAKEN, "taken": True}
    return {"message": f"Вызов брошен: район №{issued.district_number}, {issued.city_name}. Ждём ответа защитника.", "taken": False}
