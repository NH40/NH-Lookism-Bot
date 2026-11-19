"""API-роутер Mini App: онлайн-бои (`services/arena`) — старт, состояние, ход, автоатака."""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user_id
from api.db import get_session
from api.deps import get_redis
from api.routers._common import bad, cooldown_text, require_user
from bot.services import arena as svc

router = APIRouter(prefix="/api/arena", tags=["arena"])

_ERRORS = {"no_battle": "Бой уже закончен.", "not_yours": "Это не твой бой.", "in_battle": "Ты уже в бою — сначала доиграй его."}


class StartDistrictIn(BaseModel):
    district_id: int
    auto: bool = False


class ActIn(BaseModel):
    kind: str  # attack | defend | perk
    perk: str | None = None
    score: float | None = None  # мини-игра своего перка (0..1)
    game_score: float | None = None  # навязанная мини-игра (0..1)


class AutoIn(BaseModel):
    on: bool


def view(st: dict, user_id: int) -> dict:
    me = "a" if st["a"]["uid"] == user_id else "d"
    foe = "d" if me == "a" else "a"
    s, o = st[me], st[foe]
    return {
        "id": st["id"], "kind": st["kind"], "status": st["status"], "round": st["round"],
        "left": max(0, int(st["deadline"] - time.time())),
        "me": {"name": s["name"], "power": s["power"], "energy": s["energy"], "emax": s.get("emax", 10), "auto": s["auto"],
               "waiting": s["action"] is not None, "game": s["pending_game"]},
        "foe": {"name": o["name"], "power": o["power"], "energy": o["energy"], "auto": o["auto"]},
        "perks": [{"code": p.code, "name": p.name, "about": p.about, "cost": p.cost, "ready_in": p.ready_in, "affordable": p.affordable}
                  for p in svc.perks_view(st, me)],
        "log": [{"me": e[me]["code"], "foe": e[foe]["code"], "kills": e["kills"][0 if me == "a" else 1],
                 "lost": e["kills"][1 if me == "a" else 0]} for e in st["log"][-10:]],
        "result": st["result"], "report": st.get("report"), "won": (st["result"]["attacker_won"] == (me == "a")) if st["result"] else None,
    }


async def _get(redis: Redis, battle_id: str) -> dict:
    st = await svc.tick(redis, battle_id)  # вышло время — раунд разыгрывается при опросе
    if st is None:
        raise bad(_ERRORS["no_battle"])
    return st


@router.post("/start/district")
async def start_district(body: StartDistrictIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                         redis: Redis = Depends(get_redis)) -> dict:
    from api.routers import district as dr
    from bot.services import district as d

    user = await require_user(session, user_id)
    try:
        st = await svc.start_district(session, redis, user, body.district_id, auto=body.auto)
    except svc.ArenaError as exc:
        raise bad(_ERRORS.get(exc.code, "Не вышло."))
    except d.PlayerDistrictError:
        raise bad("Этот район держит игрок — брось ему вызов.")
    except (d.DistrictNotFoundError, d.NotYourCityError):
        raise bad(dr.NOT_FOUND)
    except d.OwnDistrictError:
        raise bad(dr.OWN_DISTRICT)
    except d.EmperorNoConquestError:
        raise bad(dr.EMPEROR_NO_CONQUEST)
    except d.CityConquerorError:
        raise bad(dr.CITY_CONQUEROR)
    except d.NoAttackersError:
        raise bad(dr.NO_ATTACKERS)
    except d.BattleOnCooldownError as exc:
        raise bad(cooldown_text(dr.BATTLE_PREFIX, exc.retry_after_seconds))
    if body.auto:
        st = await svc.run_auto(redis, st)
    return view(st, user_id)


class StartChallengeIn(BaseModel):
    challenge_id: int


@router.post("/start/challenge")
async def start_challenge(body: StartChallengeIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                          redis: Redis = Depends(get_redis)) -> dict:
    """Защитник принимает вызов онлайн; просроченный — разрешается автобоем лагерем защиты (как раньше)."""
    from bot.services.district.challenge import ChallengeNotFoundError

    user = await require_user(session, user_id)
    try:
        st = await svc.start_challenge(session, redis, user, body.challenge_id)
    except ChallengeNotFoundError:
        raise bad("Вызов уже неактуален.")
    except svc.ArenaError as exc:
        raise bad(_ERRORS.get(exc.code, "Не вышло."))
    if not isinstance(st, dict):  # автобой (просрочен) или аннулирован
        return {"id": None, "status": "resolved", "won": not st.attacker_won}
    return view(st, user_id)


@router.get("/current")
async def current(user_id: int = Depends(get_current_user_id), redis: Redis = Depends(get_redis)) -> dict:
    battle_id = await svc.current_of(redis, user_id)
    return {"id": battle_id}


@router.get("/{battle_id}")
async def get_battle(battle_id: str, user_id: int = Depends(get_current_user_id), redis: Redis = Depends(get_redis)) -> dict:
    st = await _get(redis, battle_id)
    if user_id not in (st["a"]["uid"], st["d"]["uid"]):
        raise bad(_ERRORS["not_yours"])
    return view(st, user_id)


@router.post("/{battle_id}/act")
async def act(battle_id: str, body: ActIn, user_id: int = Depends(get_current_user_id), redis: Redis = Depends(get_redis)) -> dict:
    action = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        st = await svc.act(redis, battle_id, user_id, action)
    except svc.ArenaError as exc:
        raise bad(_ERRORS.get(exc.code, "Не вышло."))
    return view(st, user_id)


@router.post("/{battle_id}/auto")
async def auto(battle_id: str, body: AutoIn, user_id: int = Depends(get_current_user_id), redis: Redis = Depends(get_redis)) -> dict:
    try:
        st = await svc.set_auto(redis, battle_id, user_id, body.on)
    except svc.ArenaError as exc:
        raise bad(_ERRORS.get(exc.code, "Не вышло."))
    return view(st, user_id)
