"""API-роутер Mini App: лига-обучение — те же сервисы, что у бота (`services/tutorial`)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.deps import get_redis
from api.routers._common import bad, clean_label, require_user
from bot.config.tutorial import TRAINING_LESSONS, TRAINING_POWER_DISTRICTS, TRAINING_REWARDS, TRAINING_STEPS
from bot.handlers.tutorial.tutorial import advance_text, error_text, reward_text
from bot.services import tutorial as svc
from bot.texts.tutorial import BUILT, COLLECTED, FIGHT_LOST, FIGHT_WON, NOT_YET, NOTHING_TO_COLLECT, STEP_TEXTS, STEP_TITLES
from bot.utils.formatting import format_number

router = APIRouter(prefix="/api/tutorial", tags=["tutorial"])

_GOTO = {"recruit": "/map/gang", "develop": "/stats", "bloodline": "/development", "genius": "/development",
         "technique": "/development", "mastery": "/development/mastery"}


class TargetIn(BaseModel):
    city: int
    district: int | None = None


async def _do(coro):
    try:
        return await coro
    except svc.TutorialError as exc:
        raise bad(clean_label(error_text(exc)))


def _adv(adv) -> dict:
    return {"done": [STEP_TITLES[c] for c in adv.done], "finished": adv.finished, "note": clean_label(advance_text(adv))} if adv else {"done": [], "finished": False, "note": ""}


@router.get("")
async def get_tutorial(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis)) -> dict:
    await require_user(session, user_id)
    v = await svc.view(session, redis, user_id)
    return {
        "status": v.status, "voluntary": v.voluntary, "step": v.step, "total": len(TRAINING_STEPS), "code": v.code,
        "title": clean_label(STEP_TITLES[v.code]) if v.code else None,
        "text": clean_label(STEP_TEXTS[v.code].format(need=TRAINING_POWER_DISTRICTS)) if v.code else None,
        "lesson": v.code in TRAINING_LESSONS, "goto": _GOTO.get(v.code or ""),
        "reward": clean_label(reward_text(TRAINING_REWARDS.get(v.code, {}))) if v.code else None,
        "cooldown": v.cooldown, "pending_income": v.pending_income, "capacity": v.capacity,
        "cities": [{"index": c.index, "name": c.name, "owned": c.owned, "buildings": c.buildings, "bot_rank": c.bot_rank, "bots": c.bots,
                    "whole": c.whole, "open": c.open} for c in v.cities],
    }


@router.post("/start")
async def start(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await require_user(session, user_id)
    await _do(svc.start_voluntary(session, user_id))
    return {"message": "Обучение началось."}


@router.post("/attack")
async def attack(body: TargetIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session), redis: Redis = Depends(get_redis)) -> dict:
    await require_user(session, user_id)
    report, adv = await _do(svc.attack(session, redis, user_id, body.city, body.district))
    msg = (FIGHT_WON if report.won else FIGHT_LOST).format(city=report.city, captured=report.captured, dead=format_number(report.dead), attackers=format_number(report.attackers))
    return {"message": msg, "won": report.won, **_adv(adv)}


@router.post("/build")
async def build(body: TargetIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await require_user(session, user_id)
    cost, adv = await _do(svc.build(session, user_id, body.city, body.district if body.district is not None else -1))
    return {"message": BUILT.format(cost=f" за {format_number(cost)} NHCoin" if cost else " бесплатно"), **_adv(adv)}


@router.post("/collect")
async def collect(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await require_user(session, user_id)
    amount, adv = await _do(svc.collect(session, user_id))
    return {"message": clean_label(COLLECTED.format(amount=format_number(amount))) if amount else NOTHING_TO_COLLECT, **_adv(adv)}


@router.post("/check")
async def check(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    await require_user(session, user_id)
    adv = await _do(svc.acknowledge(session, user_id))
    if not adv.done:
        raise bad(NOT_YET)
    return {"message": "Шаг пройден!", **_adv(adv)}
