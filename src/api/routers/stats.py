"""Характеристики в Mini App — ранги, очки развития, вложение очков (+1 / +5 / максимум).
Логика — `services/characteristic` (та же, что у экрана характеристик бота)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.push import with_bot_session
from api.routers._common import bad, clean_label, require_user
from api.routers.profile import plain
from bot.constant.characteristic import STATS_UP_FIVE, STATS_UP_MAX, STATS_UP_ONE
from bot.services.characteristic import NotEnoughPointsError, StatMaxedError, UnknownStatError, get_stats_view, invest
from bot.services.mastery import check_unlock
from bot.services.unique_path import check_conviction
from bot.texts.profile import POTENTIAL_LABELS, STAT_EFFECTS, STAT_INVESTED, STAT_LABELS, STAT_MAXED, STAT_NOT_ENOUGH
from bot.texts.unique_path import CONVICTION_PUSH
from bot.utils.formatting import format_number

router = APIRouter(prefix="/api/stats", tags=["stats"])


class StatOut(BaseModel):
    code: str
    label: str
    rank: str
    effect: str
    next_cost: int | None  # None — уже максимум


class StatsOut(BaseModel):
    stats: list[StatOut]
    potential: str
    dev_points: int
    strength_power_percent: int
    modes: list[str]  # +1 / +5 / максимум — значения `mode` для POST /up


@router.get("", response_model=StatsOut)
async def get_stats(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> StatsOut:
    await require_user(session, user_id)
    view = await get_stats_view(session, user_id)
    return StatsOut(
        stats=[
            StatOut(code=s.code, label=plain(STAT_LABELS[s.code]), rank=s.rank, effect=STAT_EFFECTS[s.code], next_cost=s.next_cost)
            for s in view.stats
        ],
        potential=clean_label(POTENTIAL_LABELS[view.potential]), dev_points=view.dev_points,
        strength_power_percent=view.strength_power_percent, modes=[STATS_UP_ONE, STATS_UP_FIVE, STATS_UP_MAX],
    )


class UpIn(BaseModel):
    stat: str
    mode: str


class MessageOut(BaseModel):
    message: str


@router.post("/up", response_model=MessageOut)
async def post_up(body: UpIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> MessageOut:
    await require_user(session, user_id)
    try:
        result = await invest(session, user_id, body.stat, body.mode)
    except UnknownStatError:
        raise bad("Неизвестная характеристика.")
    except StatMaxedError:
        raise bad(STAT_MAXED)
    except NotEnoughPointsError as exc:
        raise bad(STAT_NOT_ENOUGH.format(cost=exc.cost, points=format_number(exc.points)))
    # Как в боте: все четыре на EXR — задание «Преодоление стены»; «подтверждение убеждений» пути.
    await check_unlock(session, user_id)
    if await check_conviction(session, user_id):
        await with_bot_session(lambda bot, _s: bot.send_message(user_id, CONVICTION_PUSH))
    return MessageOut(message=STAT_INVESTED.format(
        label=plain(STAT_LABELS[result.stat]), ranks=result.ranks, rank=result.new_rank, cost=result.cost,
    ))
