"""API-роутер Mini App: топ игроков/кланов с наградами сезона и список всех игроков.

Только `bot.services.top` (тот же сервис, что `/top` и `/players` в боте).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from bot.config.top import PLAYERS_PAGE_SIZE, clan_reward, player_reward
from bot.services.top import get_players_page, get_top
from bot.texts.profile import PHASE_LABELS
from bot.texts.top import reward_text

router = APIRouter(prefix="/api/top", tags=["top"])


class TopPlayerOut(BaseModel):
    place: int
    user_id: int
    name: str
    phase: str
    power: int
    clan: str | None
    reward: str
    is_me: bool


class TopClanOut(BaseModel):
    place: int
    name: str
    lands: int
    members: int
    reward: str


class TopOut(BaseModel):
    players: list[TopPlayerOut]
    clans: list[TopClanOut]
    my_place: int | None
    my_power: int
    season_ends_in: int | None


class PlayersOut(BaseModel):
    players: list[TopPlayerOut]
    page: int
    pages: int
    total: int


def _player(place: int, p, me: int, reward: str = "") -> TopPlayerOut:
    return TopPlayerOut(
        place=place, user_id=p.user_id, name=p.name, phase=PHASE_LABELS.get(p.phase, p.phase), power=p.power,
        clan=p.clan, reward=reward, is_me=p.user_id == me,
    )


@router.get("", response_model=TopOut)
async def top(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> TopOut:
    view = await get_top(session, user_id)
    return TopOut(
        players=[_player(i, p, user_id, reward_text(*player_reward(i))) for i, p in enumerate(view.players, start=1)],
        clans=[
            TopClanOut(place=i, name=c.name, lands=c.lands, members=c.members, reward=reward_text(*clan_reward(i)))
            for i, c in enumerate(view.clans, start=1)
        ],
        my_place=view.my_place,
        my_power=view.my_power,
        season_ends_in=view.season_ends_in,
    )


@router.get("/players", response_model=PlayersOut)
async def players(
    page: int = 0, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)
) -> PlayersOut:
    rows, page, pages, total = await get_players_page(session, page, PLAYERS_PAGE_SIZE)
    start = page * PLAYERS_PAGE_SIZE
    return PlayersOut(
        players=[_player(start + i, p, user_id) for i, p in enumerate(rows, start=1)], page=page, pages=pages, total=total
    )
