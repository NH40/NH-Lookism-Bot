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

_ERRORS = {"no_battle": "Бой уже закончен.", "not_yours": "Это не твой бой.", "in_battle": "Ты уже в бою — сначала доиграй его.",
           "no_army": "В лагере атаки нет статистов."}
_START_ERRORS = {  # имя исключения сервиса → текст (босс, город, рейд, война)
    "EventGoneError": "Босс уже ушёл.", "BossAlreadyDefeatedError": "Этого босса ты уже победил.",
    "NotCityConquerorError": "Брать город целиком может только круг.", "CityNotInCountryError": "Город не найден.",
    "NoBotsInCityError": "В городе не осталось районов у ботов.", "EmperorNoConquestError": "Император не захватывает районы.",
    "NoAttackersError": "В лагере атаки нет статистов.", "RaidError": "Рейда сейчас нет.", "WarNotFoundError": "Война уже неактуальна.",
}


async def _start(coro, user_id: int) -> dict:
    """Старт онлайн-боя: ошибки сервиса → 400 с текстом; бой начат → вид для игрока; автобой (просрочено) → итог."""
    try:
        st = await coro
    except svc.ArenaError as exc:
        raise bad(_ERRORS.get(exc.code, "Не вышло."))
    except Exception as exc:  # noqa: BLE001
        name = type(exc).__name__
        if name == "BattleOnCooldownError":
            raise bad(cooldown_text("Сражение", exc.retry_after_seconds))
        if name in _START_ERRORS:
            raise bad(_START_ERRORS[name])
        raise
    if not isinstance(st, dict):
        return {"id": None, "status": "resolved"}
    return view(st, user_id)


class StartBossIn(BaseModel):
    event_id: int


class StartCityIn(BaseModel):
    city_id: int


class StartWarIn(BaseModel):
    war_id: int


@router.post("/start/boss")
async def start_boss(body: StartBossIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                     redis: Redis = Depends(get_redis)) -> dict:
    user = await require_user(session, user_id)
    return await _start(svc.start_boss(session, redis, user, body.event_id), user_id)


@router.post("/start/city")
async def start_city(body: StartCityIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                     redis: Redis = Depends(get_redis)) -> dict:
    user = await require_user(session, user_id)
    return await _start(svc.start_city(session, redis, user, body.city_id), user_id)


@router.post("/start/raid")
async def start_raid(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                     redis: Redis = Depends(get_redis)) -> dict:
    user = await require_user(session, user_id)
    return await _start(svc.start_raid(session, redis, user), user_id)


@router.post("/start/war")
async def start_war(body: StartWarIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session),
                    redis: Redis = Depends(get_redis)) -> dict:
    await require_user(session, user_id)
    return await _start(svc.start_war(session, redis, user_id, body.war_id), user_id)


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


def _act_name(code: str | None) -> str:
    if code in (None, "", "attack"):
        return "Атака"
    if code == "defend":
        return "Защита"
    perk = svc.PERK_REGISTRY.get(code)
    return perk.name if perk else "Перк"


def view(st: dict, user_id: int) -> dict:
    me = "a" if st["a"]["uid"] == user_id else "d"
    foe = "d" if me == "a" else "a"
    s, o = st[me], st[foe]
    return {
        "id": st["id"], "kind": st["kind"], "status": st["status"], "round": st["round"],
        "left": max(0, int(st["deadline"] - time.time())),
        "me": {"name": s["name"], "power": s["power"], "energy": s["energy"], "emax": s.get("emax", 10), "auto": s["auto"],
               "waiting": s["action"] is not None, "game": s["pending_game"] if s["pending_game"] and not s["pending_game"].get("played") else None, "power0": s.get("power0", s["power"]), "afk": s.get("afk", False),
               "ava": s.get("ava"), "bot": s["uid"] is None,
               "chosen": _act_name((s["action"] or {}).get("perk") or (s["action"] or {}).get("kind")) if s["action"] else None,
               "units": s.get("units"), "units0": s.get("units0")},
        "foe": {"name": o["name"], "power": o["power"], "energy": o["energy"], "emax": o.get("emax", 10), "auto": o["auto"], "afk": o.get("afk", False),
                "ava": o.get("ava"), "bot": o["uid"] is None,
                "waiting": o["action"] is not None, "power0": o.get("power0", o["power"]), "units": o.get("units"), "units0": o.get("units0")},
        "perks": [{"code": p.code, "name": p.name, "about": p.about, "cost": p.cost, "ready_in": p.ready_in, "affordable": p.affordable,
                   "minigame": svc.PERK_REGISTRY[p.code].minigame, "game": svc.PERK_REGISTRY[p.code].game}
                  for p in svc.perks_view(st, me)],
        "log": [{"round": n, "me": e[me]["code"], "foe": e[foe]["code"], "me_name": _act_name(e[me]["code"]), "foe_name": _act_name(e[foe]["code"]),
                 "kills": e["kills"][0 if me == "a" else 1], "lost": e["kills"][1 if me == "a" else 0],
                 "hit": e.get("hit", [0, 0])[0 if me == "a" else 1], "taken": e.get("hit", [0, 0])[1 if me == "a" else 0],
                 "fired": e.get("fired", [[], []])[0 if me == "a" else 1], "foe_fired": e.get("fired", [[], []])[1 if me == "a" else 0]}
                for n, e in list(enumerate(st["log"], 1))[-12:]],
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


class PerkToggleIn(BaseModel):
    code: str
    off: bool


_SOURCE_NAMES = {"base": "Базовый", "tech": "Техника", "path": "Путь", "blood": "Родословная", "abs": "Абсолют",
                 "pos": "Позиция банды", "mt": "Техника мастерства"}


@router.get("/perks")
async def my_perks(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    """Способности для онлайн-боёв (2026-11-20): все доступные перки игрока и какие отключены."""
    from sqlalchemy import select

    from bot.db.models.user import User
    from bot.services.arena.sources import perks_for

    codes = await perks_for(session, user_id, include_off=True)
    off = set(await session.scalar(select(User.arena_perks_off).where(User.id == user_id)) or [])
    out = []
    for c in codes:
        p = svc.PERK_REGISTRY[c]
        src = c.split(":", 1)[0] if ":" in c else "base"
        out.append({"code": c, "name": p.name, "about": p.about, "cost": p.cost, "cooldown": p.cooldown,
                    "minigame": p.minigame, "source": _SOURCE_NAMES.get(src, "Другое"), "off": c in off})
    return {"perks": out}


@router.post("/perks")
async def toggle_perk(body: PerkToggleIn, user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    from sqlalchemy import select, update

    from bot.db.models.user import User

    off = list(await session.scalar(select(User.arena_perks_off).where(User.id == user_id)) or [])
    if body.off and body.code not in off:
        off.append(body.code)
    if not body.off:
        off = [c for c in off if c != body.code]
    await session.execute(update(User).where(User.id == user_id).values(arena_perks_off=off))
    await session.commit()
    return await my_perks(user_id, session)


@router.get("/challenges")
async def my_challenges(user_id: int = Depends(get_current_user_id), session: AsyncSession = Depends(get_session)) -> dict:
    """Вызовы игрока (2026-11-20): ждущие ответа (свои и входящие) и итоги за 2 часа — чтобы было видно, принял ли соперник."""
    from sqlalchemy import text

    rows = (await session.execute(text(
        """SELECT c.id, c.attacker_id = :u, CASE WHEN c.attacker_id = :u THEN gd.name ELSE ga.name END, d.number, ci.name,
                  c.status, c.resolution, c.attacker_won,
                  greatest(0, extract(epoch FROM c.expires_at - now()))::int, extract(epoch FROM now() - c.resolved_at)::int
           FROM district_challenges c LEFT JOIN districts d ON d.id = c.district_id LEFT JOIN cities ci ON ci.id = c.city_id
           LEFT JOIN gangs ga ON ga.user_id = c.attacker_id LEFT JOIN gangs gd ON gd.user_id = c.defender_id
           WHERE (c.attacker_id = :u OR c.defender_id = :u)
             AND (c.status = 'pending' OR (c.resolved_at > now() - interval '2 hours' AND c.resolution IN ('accepted', 'timeout')))
           ORDER BY c.status = 'pending' DESC, coalesce(c.resolved_at, c.created_at) DESC LIMIT 8"""), {"u": user_id})).all()
    return {"items": [{
        "id": cid, "out": out, "other": other or "—", "target": f"район №{num}" if num else f"город {city}" if city else "земли",
        "pending": status == "pending", "resolution": res, "won": (won if out else (not won if won is not None else None)),
        "expires_in": exp, "ago": ago,
    } for cid, out, other, num, city, status, res, won, exp, ago in rows]}


@router.get("/current")
async def current(user_id: int = Depends(get_current_user_id), redis: Redis = Depends(get_redis)) -> dict:
    battle_id = await svc.current_of(redis, user_id)
    return {"id": battle_id}


async def _ensure_avatars(session: AsyncSession, redis: Redis, st: dict) -> None:
    """Аватарки сторон (2026-11-20): уник на позиции лидера банды. Считаются один раз и хранятся в состоянии боя."""
    if all("ava" in st[x] for x in ("a", "d")):
        return
    from bot.services.profile.summary import _avatar

    for x in ("a", "d"):
        if "ava" not in st[x]:
            st[x]["ava"] = await _avatar(session, st[x]["uid"]) if st[x]["uid"] else None
    if st["status"] == svc.STATUS_LIVE:
        await svc.save(redis, st)


@router.get("/{battle_id}")
async def get_battle(battle_id: str, user_id: int = Depends(get_current_user_id), redis: Redis = Depends(get_redis),
                     session: AsyncSession = Depends(get_session)) -> dict:
    st = await _get(redis, battle_id)
    if user_id not in (st["a"]["uid"], st["d"]["uid"]):
        raise bad(_ERRORS["not_yours"])
    await _ensure_avatars(session, redis, st)
    await svc.mark_seen(redis, st, user_id)
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
