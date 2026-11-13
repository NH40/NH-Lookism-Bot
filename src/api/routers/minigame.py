"""API мини-игр занятий техники и испытаний мастерства. Логика — `bot.services.minigame`."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.deps import get_redis
from api.routers._common import bad
from bot.services import minigame as svc

router = APIRouter(prefix="/api/minigame", tags=["minigame"])

_ERRORS = {
    "unknown": "Неизвестная игра.",
    "no_lesson": "Занятие не оплачено — купи его у учителя в Тренировках.",
    "locked": "Этот этап пока закрыт.",
    "done": "Этап уже пройден.",
    "expired": "Игра устарела — начни этап заново.",
    "too_fast": "Слишком быстро — начни этап заново.",
    "failed": "Не получилось — попробуй ещё раз, это бесплатно.",
}


def _board(b: svc.Board) -> dict:
    return {
        "ctx": b.ctx, "code": b.title_code, "level": b.level,
        "stages": [{"game": s.game, "done": s.done, "playable": s.playable} for s in b.stages],
    }


@router.get("")
async def get_board(ctx: str, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    try:
        return _board(await svc.board(session, user_id, ctx))
    except svc.MinigameError as exc:
        raise bad(_ERRORS[exc.code])


class StartIn(BaseModel):
    ctx: str
    stage: int


@router.post("/start")
async def post_start(body: StartIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                     redis: Redis = Depends(get_redis)) -> dict:
    try:
        return await svc.start(session, redis, user_id, body.ctx, body.stage)
    except svc.MinigameError as exc:
        raise bad(_ERRORS[exc.code])


class FinishIn(BaseModel):
    token: str
    score: int


@router.post("/finish")
async def post_finish(body: FinishIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                      redis: Redis = Depends(get_redis)) -> dict:
    try:
        return {"ok": True, "board": _board(await svc.finish(session, redis, user_id, body.token, body.score))}
    except svc.MinigameError as exc:
        return {"ok": False, "message": _ERRORS[exc.code]}
