"""API-роутер Mini App: мастерство — цепочка «Преодоление стены», бой с Томом Ли, тренер, очки.

Бизнес-логика — только `bot.services.mastery` и `bot.services.district.fight_tom` (те же, что
вызывает `bot.handlers.mastery`); роутер валидирует запрос и собирает ответ экрана.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.deps import get_redis
from api.routers.profile import plain
from bot.cache.keys import battle_cooldown
from bot.config.characteristic import (
    endurance_mastery_loss_save_percent,
    speed_mastery_cd_reduction_percent,
    strength_mastery_power_percent,
    technique_mastery_multiplier,
)
from bot.config.mastery import MASTERY_POINTS_PER_STAGE, MASTERY_STAGES
from bot.constant.characteristic import MASTERIES, MASTERY_ENDURANCE, MASTERY_SPEED, MASTERY_STRENGTH
from bot.db.repositories import business as business_repo
from bot.db.repositories.user import get_by_id
from bot.services.district import BattleOnCooldownError, NoAttackersError, fight_tom
from bot.services.mastery import (
    MasteryCappedError,
    NoFreePointsError,
    NotEnoughCoinsError,
    PointsSoldOutError,
    QuestNotActiveError,
    TomLockedError,
    TrainerLockedError,
    buy_point,
    get_view,
    invest_point,
)
from bot.texts.district import NO_ATTACKERS
from bot.texts.mastery import (
    MASTERY_CAPPED_ALERT,
    NO_FREE_POINTS_ALERT,
    QUEST_NOT_ACTIVE_ALERT,
    STAGE_NAMES,
    TASK_LABELS,
    TOM_LOCKED_ALERT,
)
from bot.texts.profile import MASTERY_LABELS, MASTERY_TIER_LABELS
from bot.utils.formatting import format_countdown, format_number

router = APIRouter(prefix="/api/mastery", tags=["mastery"])


class MasteryTierOut(BaseModel):
    code: str
    label: str
    tier: int
    tier_label: str
    effect: str
    can_invest: bool


class MasteryTaskOut(BaseModel):
    label: str
    progress: int
    target: int
    done: bool
    locked: bool


class MasteryOut(BaseModel):
    tiers: list[MasteryTierOut]
    status: str | None  # None — цепочка не открыта; pending/active/trainer/complete
    stage: int
    stages: int
    stage_name: str
    tasks: list[MasteryTaskOut]
    tom_power: int
    tom_unlocked: bool
    points_bought: int
    points_free: int
    points_per_stage: int
    price: int | None
    available_in_seconds: int | None
    nh_coins: int
    battle_cooldown_seconds: int


def _effect(code: str, tier: int) -> str:
    if tier <= 0:
        return "нет бонуса"
    if code == MASTERY_STRENGTH:
        return f"+{strength_mastery_power_percent(tier)}% к мощи армии"
    if code == MASTERY_SPEED:
        return f"−{speed_mastery_cd_reduction_percent(tier)}% к кулдаунам"
    if code == MASTERY_ENDURANCE:
        return f"{endurance_mastery_loss_save_percent(tier)}% потерь в бою спасается"
    return f"эффекты техники ×{technique_mastery_multiplier(tier)}"


def bad(message: str) -> HTTPException:
    return HTTPException(400, message)


async def _onboarded(session: AsyncSession, user_id: int):
    user = await get_by_id(session, user_id)
    if user is None or user.city_id is None:
        raise HTTPException(404, "Игрок не найден")
    return user


@router.get("", response_model=MasteryOut)
async def get_mastery(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> MasteryOut:
    await _onboarded(session, user_id)
    view = await get_view(session, user_id)
    wallet = await business_repo.get_wallet(session, user_id)
    free = view.points_free > 0
    return MasteryOut(
        tiers=[
            MasteryTierOut(
                code=code, label=plain(MASTERY_LABELS[code]), tier=view.mastery[code],
                tier_label=MASTERY_TIER_LABELS[view.mastery[code]], effect=_effect(code, view.mastery[code]),
                can_invest=free and view.mastery[code] < view.stage,
            )
            for code in MASTERIES
        ],
        status=view.status,
        stage=view.stage,
        stages=MASTERY_STAGES,
        stage_name=STAGE_NAMES.get(view.stage, ""),
        tasks=[
            MasteryTaskOut(label=TASK_LABELS[t.code], progress=t.progress, target=t.target, done=t.done, locked=t.locked)
            for t in view.tasks
        ],
        tom_power=view.tom_power,
        tom_unlocked=view.tom_unlocked,
        points_bought=view.points_bought,
        points_free=view.points_free,
        points_per_stage=MASTERY_POINTS_PER_STAGE,
        price=view.price,
        available_in_seconds=view.available_in_seconds,
        nh_coins=wallet.nh_coins if wallet else 0,
        battle_cooldown_seconds=max(0, await redis.ttl(battle_cooldown(user_id))),
    )


@router.post("/tom")
async def post_tom(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    user = await _onboarded(session, user_id)
    try:
        result = await fight_tom(session, redis, user)
    except QuestNotActiveError:
        raise bad(QUEST_NOT_ACTIVE_ALERT)
    except TomLockedError:
        raise bad(TOM_LOCKED_ALERT)
    except NoAttackersError:
        raise bad(NO_ATTACKERS)
    except BattleOnCooldownError as exc:
        raise bad(f"Сражение ещё на кулдауне — через {format_countdown(exc.retry_after_seconds)}.")
    return {
        "message": "Победа над Томом Ли! Тренер ждёт — покупай очки мастерства." if result.won else "Поражение — Том оказался сильнее.",
        "won": result.won,
        "rounds": result.rounds,
        "attacker_power": result.attacker_power,
        "attacker_dead": result.attacker_dead,
        "tom_power": result.tom_power,
        "tom_remaining_power": result.tom_remaining_power,
    }


@router.post("/buy")
async def post_buy(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    try:
        result = await buy_point(session, user_id)
    except TrainerLockedError:
        raise bad("Тренер Том Ли откроется после победы над ним.")
    except PointsSoldOutError:
        raise bad("Все очки этого этапа уже куплены.")
    except NotEnoughCoinsError as exc:
        raise bad(f"Не хватает NHCoin: нужно {format_number(exc.cost)}, у тебя {format_number(exc.balance)}.")
    return {"message": f"Куплено очко мастерства ({result.points_bought}/{MASTERY_POINTS_PER_STAGE})", "points_free": result.points_free}


class InvestIn(BaseModel):
    mastery: str


@router.post("/invest")
async def post_invest(
    body: InvestIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> dict:
    try:
        result = await invest_point(session, user_id, body.mastery)
    except NoFreePointsError:
        raise bad(NO_FREE_POINTS_ALERT)
    except MasteryCappedError:
        raise bad(MASTERY_CAPPED_ALERT)
    label, tier = plain(MASTERY_LABELS[result.mastery]), MASTERY_TIER_LABELS[result.new_tier]
    if result.chain_complete:
        message = f"{label}: {tier}. Мастерство постигнуто!"
    elif result.stage_finished:
        message = f"{label}: {tier}. Этап пройден — следующее задание придёт в течение суток."
    else:
        message = f"{label}: {tier}"
    return {"message": message}
