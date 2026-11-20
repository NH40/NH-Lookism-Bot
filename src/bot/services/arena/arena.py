"""Онлайн-бои — ядро (сервис, пользователь 2026-11-19). Баланс — `config/arena`, перки — `config/arena/perks`.

Бой живёт в Redis (JSON + снимок армий), без таблиц: памяти почти не ест, после боя исчезает. Каждый раунд бой
пересобирается из снимка с тем же зерном и уже сыгранными действиями (`BattleRun` детерминирован), поэтому между
запросами ничего, кроме JSON, хранить не нужно.

Ход раунда: стороны выбирают действие (атака / защита / перк). Сторона на автоатаке, не сходившая до конца
таймера или без игрока (бот, рота защиты) — ходит за неё ИИ «нормального» уровня. Когда сходили обе или вышло
время — раунд разыгрывается. Итог боя применяет сценарий (`register_finisher`) — захват района, трон и т. д.
"""
from __future__ import annotations

import base64
import json
import pickle
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from random import Random

from redis.asyncio import Redis

from bot.config.arena import (
    ARENA_AI_DEFEND_RATIO,
    ARENA_AUTO_MINIGAME_SCORE,
    ARENA_DEFEND_DAMAGE,
    ARENA_DEFEND_ENERGY,
    ARENA_DEFEND_REDUCTION,
    ARENA_ENERGY_MAX,
    ARENA_ENERGY_REGEN,
    ARENA_ENERGY_START,
    ARENA_ROUND_SECONDS,
    ARENA_TTL_SECONDS,
)
from bot.config.arena.perks import BASE_PERKS, Perk
from bot.services.combat import BattleRun, CombatChances, CombatStack
from bot.services.combat.combat import BattleResult
from bot.services.combat.mods import CombatMods

ATTACK, DEFEND, PERK = "attack", "defend", "perk"
SIDES = ("a", "d")
STATUS_LIVE, STATUS_DONE = "live", "done"
LIVE_SET = "arena:live"  # идущие бои — для фонового прохода по таймерам
_DEFEND_MODS = CombatMods(reduction=ARENA_DEFEND_REDUCTION)

Finisher = Callable[[Redis, dict, BattleResult], Awaitable[None]]
_FINISHERS: dict[str, Finisher] = {}
PERK_REGISTRY: dict[str, Perk] = dict(BASE_PERKS)


def _load_sources() -> None:
    from bot.config.arena.sources import build_source_perks

    PERK_REGISTRY.update(build_source_perks())


_load_sources()


class ArenaError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def register_finisher(kind: str, fn: Finisher) -> None:
    """Сценарий боя (`kind`) применяет итог: потери, захват, награды. Вызывается один раз, когда бой закончен."""
    _FINISHERS[kind] = fn


def _key(battle_id: str) -> str:
    return f"arena:{battle_id}"


def _user_key(user_id: int) -> str:
    return f"arena:user:{user_id}"


def _pack(obj) -> str:
    return base64.b64encode(pickle.dumps(obj)).decode()


def _unpack(raw: str):
    return pickle.loads(base64.b64decode(raw))  # noqa: S301 — свои же данные из Redis


async def load(redis: Redis, battle_id: str) -> dict | None:
    raw = await redis.get(_key(battle_id))
    return json.loads(raw) if raw else None


async def _save(redis: Redis, st: dict) -> None:
    await redis.set(_key(st["id"]), json.dumps(st), ex=ARENA_TTL_SECONDS)
    if st["status"] == STATUS_LIVE:
        await redis.sadd(LIVE_SET, st["id"])
    else:
        await redis.srem(LIVE_SET, st["id"])
    for side in SIDES:
        uid = st[side]["uid"]
        if uid:
            if st["status"] == STATUS_LIVE:
                await redis.set(_user_key(uid), st["id"], ex=ARENA_TTL_SECONDS)
            else:
                await redis.delete(_user_key(uid))


async def current_of(redis: Redis, user_id: int) -> str | None:
    return await redis.get(_user_key(user_id))


async def create(
    redis: Redis, *, kind: str,
    a_uid: int | None, d_uid: int | None,
    a_stacks: list[CombatStack], d_stacks: list[CombatStack],
    a_chances: CombatChances, d_chances: CombatChances,
    a_perks: list[str], d_perks: list[str],
    a_auto: bool, d_auto: bool,
    a_name: str, d_name: str,
    meta: dict | None = None,
    a_energy: tuple[int, int, int] | None = None, d_energy: tuple[int, int, int] | None = None,
) -> dict:
    """Начать бой. `*_uid` None — бот/босс (всегда автоатака). Армии и билды снимаются на старте."""
    battle_id = secrets.token_hex(8)

    def side(uid, perks, auto, name, stacks, energy):
        start, regen, cap = energy or (ARENA_ENERGY_START, ARENA_ENERGY_REGEN, ARENA_ENERGY_MAX)
        return {"uid": uid, "name": name, "auto": bool(auto or uid is None), "energy": start, "regen": regen, "emax": cap, "cd": {},
                "perks": [p for p in perks if p in PERK_REGISTRY], "action": None, "pending_game": None,
                "power": int(sum(s.unit_power * s.quantity for s in stacks)),
                "power0": int(sum(s.unit_power * s.quantity for s in stacks)), "units": int(sum(s.quantity for s in stacks)),
                "units0": int(sum(s.quantity for s in stacks))}

    st = {
        "id": battle_id, "kind": kind, "status": STATUS_LIVE, "round": 0, "seed": secrets.randbits(48),
        "deadline": time.time() + ARENA_ROUND_SECONDS, "log": [], "meta": meta or {},
        "a": side(a_uid, a_perks, a_auto, a_name, a_stacks, a_energy), "d": side(d_uid, d_perks, d_auto, d_name, d_stacks, d_energy),
        "snap": _pack((a_stacks, d_stacks, a_chances, d_chances)), "result": None,
    }
    await _save(redis, st)
    return st


def _rebuild(st: dict) -> BattleRun:
    a_stacks, d_stacks, a_ch, d_ch = _unpack(st["snap"])
    run = BattleRun(a_stacks, d_stacks, attacker_chances=a_ch, defender_chances=d_ch, rng=Random(st["seed"]))
    for entry in st["log"]:
        a_extra, d_extra = _extras(entry["a"]["code"], entry["d"]["code"])
        run.play_round(a_extra, d_extra, entry["a"]["dmg"], entry["d"]["dmg"])
    return run


def _action_mods(code: str) -> tuple[CombatMods, CombatMods]:
    """(своё, противнику) по коду действия: "attack" | "defend" | код перка."""
    if code == DEFEND:
        return _DEFEND_MODS, CombatMods()
    perk = PERK_REGISTRY.get(code)
    if perk is None:
        return CombatMods(), CombatMods()
    return perk.self_mods, perk.enemy_mods


def _extras(a_code: str, d_code: str) -> tuple[CombatMods, CombatMods]:
    a_own, a_enemy = _action_mods(a_code)
    d_own, d_enemy = _action_mods(d_code)
    return a_own + d_enemy, d_own + a_enemy


def _ready(side: dict, code: str, round_no: int) -> bool:
    perk = PERK_REGISTRY.get(code)
    return perk is not None and code in side["perks"] and side["energy"] >= perk.cost and side["cd"].get(code, 0) <= round_no


_VALUE_FIELDS = {  # вклад поля модификаторов в «силу» перка для автоатаки (грубо, в долях урона)
    "attack": 1.0, "durability": 0.6, "reduction": 1.0, "pierce": 0.5, "sure_hit": 0.5, "crit_chance": 0.8, "crit_power": 0.3,
    "heal": 1.2, "multi_hit": 0.8, "dodge": 0.8, "block": 0.6, "suppress": 0.5, "bleed": 0.6, "first_strike": 1.0, "chaos": 1.0,
}


def perk_value(p: Perk) -> float:
    """Оценка силы перка для автоатаки: прирост урона + взвешенные модификаторы + мини-игра (средне) — на единицу энергии."""
    v = (p.damage - 1) + (1 - p.enemy_damage)
    for name, w in _VALUE_FIELDS.items():
        v += w * float(getattr(p.self_mods, name, 0) or 0) + 0.5 * w * float(getattr(p.enemy_mods, name, 0) or 0)
    if p.minigame:
        v += p.power * ARENA_AUTO_MINIGAME_SCORE
    return v * p.ai_weight / max(1, p.cost) ** 0.5


def ai_action(side: dict, round_no: int, own_power: float, enemy_power: float) -> dict:
    """Автоатака «нормального» уровня: перк, если хватает энергии (самый весомый из готовых), защита — когда
    сильно проигрываешь, иначе атака. Мини-игры — средний результат."""
    ready = [PERK_REGISTRY[c] for c in side["perks"] if _ready(side, c, round_no)]
    if ready:
        best = max(ready, key=lambda p: (perk_value(p), p.code))
        return {"kind": PERK, "perk": best.code, "score": ARENA_AUTO_MINIGAME_SCORE}
    if enemy_power and own_power < enemy_power * ARENA_AI_DEFEND_RATIO:
        return {"kind": DEFEND}
    return {"kind": ATTACK}


def _resolve_action(side: dict, action: dict | None, round_no: int, own_power: float, enemy_power: float) -> tuple[str, float, Perk | None]:
    """→ (код действия, множитель своего урона от действия, перк)."""
    if action is None or side["auto"]:
        action = ai_action(side, round_no, own_power, enemy_power) if (action is None or side["auto"]) else action
    kind = action.get("kind")
    if kind == DEFEND:
        return DEFEND, ARENA_DEFEND_DAMAGE, None
    if kind == PERK and _ready(side, action.get("perk", ""), round_no):
        perk = PERK_REGISTRY[action["perk"]]
        dmg = perk.damage
        if perk.minigame == "self":
            score = max(0.0, min(1.0, float(action.get("score", 0.0))))
            dmg *= 1 + perk.power * score
        return perk.code, dmg, perk
    return ATTACK, 1.0, None


async def act(redis: Redis, battle_id: str, user_id: int, action: dict) -> dict:
    """Ход игрока. Если обе стороны готовы — раунд разыгрывается сразу. → состояние."""
    st = await load(redis, battle_id)
    if st is None or st["status"] != STATUS_LIVE:
        raise ArenaError("no_battle")
    side = _side_of(st, user_id)
    st[side]["action"] = action
    if "game_score" in action and st[side]["pending_game"]:
        st[side]["pending_game"]["score"] = max(0.0, min(1.0, float(action["game_score"])))
    other = "d" if side == "a" else "a"
    if st[other]["auto"] or st[other]["action"] is not None:
        return await _play(redis, st)
    await _save(redis, st)
    return st


async def set_auto(redis: Redis, battle_id: str, user_id: int, on: bool) -> dict:
    st = await load(redis, battle_id)
    if st is None or st["status"] != STATUS_LIVE:
        raise ArenaError("no_battle")
    side = _side_of(st, user_id)
    st[side]["auto"] = bool(on)
    other = "d" if side == "a" else "a"
    if on and (st[other]["auto"] or st[other]["action"] is not None):
        return await _play(redis, st)
    await _save(redis, st)
    return st


def _side_of(st: dict, user_id: int) -> str:
    for side in SIDES:
        if st[side]["uid"] == user_id:
            return side
    raise ArenaError("not_yours")


async def tick(redis: Redis, battle_id: str) -> dict | None:
    """Вышло время раунда — разыграть (за не сходивших — автоатака)."""
    st = await load(redis, battle_id)
    if st is None or st["status"] != STATUS_LIVE:
        return st
    if time.time() >= st["deadline"] or (st["a"]["auto"] and st["d"]["auto"]):
        return await _play(redis, st)
    return st


async def _play(redis: Redis, st: dict) -> dict:
    run = _rebuild(st)
    round_no = st["round"] + 1
    a_pow, d_pow = run.a.total_power(), run.d.total_power()
    a_code, a_dmg, a_perk = _resolve_action(st["a"], st["a"]["action"], round_no, a_pow, d_pow)
    d_code, d_dmg, d_perk = _resolve_action(st["d"], st["d"]["action"], round_no, d_pow, a_pow)
    # Чужой перк на этот раунд и навязанная в прошлом раунде мини-игра.
    for me, dmg_ref, enemy_perk in (("a", "ad", d_perk), ("d", "dd", a_perk)):
        mult = enemy_perk.enemy_damage if enemy_perk else 1.0
        pending = st[me]["pending_game"]
        if pending:
            score = ARENA_AUTO_MINIGAME_SCORE if st[me]["auto"] else pending.get("score", 0.0)
            mult *= 1 - pending["power"] * (1 - score)
        if me == "a":
            a_dmg *= mult
        else:
            d_dmg *= mult
    a_extra, d_extra = _extras(a_code, d_code)
    entry_log = run.play_round(a_extra, d_extra, a_dmg, d_dmg)
    for me, code, perk, other in (("a", a_code, a_perk, "d"), ("d", d_code, d_perk, "a")):
        s = st[me]
        s["pending_game"] = None
        if perk is not None:
            s["energy"] -= perk.cost
            s["cd"][perk.code] = round_no + perk.cooldown + 1
            if perk.minigame == "enemy":
                st[other]["pending_game"] = {"game": perk.game, "power": perk.power, "from": round_no, "score": 0.0}
        if code == DEFEND:
            s["energy"] += ARENA_DEFEND_ENERGY
        s["energy"] = min(s.get("emax", ARENA_ENERGY_MAX), s["energy"] + s.get("regen", ARENA_ENERGY_REGEN))
        s["action"] = None
    st["log"].append({"a": {"code": a_code, "dmg": a_dmg}, "d": {"code": d_code, "dmg": d_dmg},
                      "kills": [entry_log.attacker_kills, entry_log.defender_kills] if entry_log else [0, 0],
                      # для живого журнала в Mini App: урон сторон и сработавшие навыки/события раунда
                      "hit": [entry_log.attacker_damage, entry_log.defender_damage] if entry_log else [0, 0],
                      "fired": [list(entry_log.attacker_fired)[:4], list(entry_log.defender_fired)[:4]] if entry_log else [[], []]})
    st["round"] = round_no
    st["a"]["power"], st["d"]["power"] = int(run.a.total_power()), int(run.d.total_power())
    st["a"]["units"], st["d"]["units"] = int(run.a.alive_quantity()), int(run.d.alive_quantity())
    st["deadline"] = time.time() + ARENA_ROUND_SECONDS
    if run.over:
        result = run.result()
        st["status"] = STATUS_DONE
        st["result"] = {"attacker_won": result.attacker_won, "rounds": result.rounds,
                        "a_dead": result.attacker.total_dead, "d_dead": result.defender.total_dead}
        await _save(redis, st)
        fn = _FINISHERS.get(st["kind"])
        if fn is not None:
            try:
                await fn(redis, st, result)
            except Exception:  # итог не применился — бой всё равно закрыт, ошибка в журнал
                import logging

                logging.getLogger(__name__).exception("Arena finisher %s failed", st["kind"])
        return await load(redis, st["id"]) or st
    await _save(redis, st)
    return st


async def run_auto(redis: Redis, st: dict) -> dict:
    """Оба на автоатаке (офлайн-бой): доиграть сразу до конца."""
    while st["status"] == STATUS_LIVE:
        st = await _play(redis, st)
    return st


@dataclass(frozen=True, slots=True)
class PerkView:
    code: str
    name: str
    about: str
    cost: int
    ready_in: int  # раундов до готовности (0 — готов)
    affordable: bool


def perks_view(st: dict, side: str) -> list[PerkView]:
    s, next_round = st[side], st["round"] + 1
    out = []
    for code in s["perks"]:
        p = PERK_REGISTRY[code]
        out.append(PerkView(code, p.name, p.about, p.cost, max(0, s["cd"].get(code, 0) - next_round), s["energy"] >= p.cost))
    return out


async def save(redis: Redis, st: dict) -> None:
    await _save(redis, st)


async def sweep(redis: Redis) -> int:
    """Фоновый проход: раунды, у которых вышло время, — разыграть. → сколько раундов сыграно."""
    played = 0
    for battle_id in list(await redis.smembers(LIVE_SET)):
        st = await load(redis, battle_id)
        if st is None:
            await redis.srem(LIVE_SET, battle_id)
            continue
        if st["status"] == STATUS_LIVE and time.time() >= st["deadline"]:
            await tick(redis, battle_id)
            played += 1
    return played
