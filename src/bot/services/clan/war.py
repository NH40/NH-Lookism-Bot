"""Кланы — война за земли (сервис). Дизайн — `docs/design/clans.md`.

Пользователь 2026-10-04: «раз в 24 часа один клан может напасть на другой, победитель забирает
часть земель»; воюют клановые роты. Бой — тот же движок, что все бои игры: рота нападающего
(+Кузницы, +донат-уровень) против роты защитника (+Стены, +донат-уровень), потери — с рот.
Победа нападающего: доля земель защитника по перевесу (не ниже минимума у защитника, сколько
влезает в потолок нападающего) и доля казны; здания защитника сверх оставшихся земель
рушатся. Защитник после нападения — под щитом. Обе строки кланов — `FOR UPDATE` в порядке id.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.clan import (
    CLAN_DONATE_LEVELS,
    CLAN_FORGE_ATTACK,
    CLAN_PAGE,
    CLAN_WALL_DEFENSE,
    CLAN_WAR_COOLDOWN_HOURS,
    CLAN_WAR_SHIELD_HOURS,
    CLAN_WAR_TREASURY_PERCENT,
    war_lands,
)
from bot.constant.clan import BUILDING_FORGE, BUILDING_WALL, MANAGER_RANKS
from bot.db.models.clan import Clan
from bot.db.repositories import clan as clan_repo
from bot.services.clan.clan import ClanError, require_member
from bot.services.clan.economy import _lock, _name, max_lands
from bot.services.clan.garrison import apply_losses, garrison_stacks, stacks_power
from bot.services.combat import base_chances, simulate_battle
from bot.services.combat.mods import BattleBuild, CombatMods

_NO_ARMY_RATIO = 1_000_000.0


@dataclass(frozen=True, slots=True)
class WarTarget:
    clan_id: int
    name: str
    lands: int
    members: int
    shielded: bool


@dataclass(frozen=True, slots=True)
class WarOutcome:
    attacker_id: int
    defender_id: int
    attacker_name: str
    defender_name: str
    attacker_won: bool
    rounds: int
    attacker_power: int
    defender_power: int
    attacker_dead: int
    defender_dead: int
    lands_taken: int
    lands_gained: int
    treasury_taken: int
    buildings_lost: dict
    attacker_members: list[int]
    defender_members: list[int]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def cooldown_left(clan: Clan) -> int:
    if clan.last_attack_at is None:
        return 0
    return max(0, int((clan.last_attack_at + timedelta(hours=CLAN_WAR_COOLDOWN_HOURS) - _now()).total_seconds()))


def shield_left(clan: Clan) -> int:
    if clan.shield_until is None:
        return 0
    return max(0, int((clan.shield_until - _now()).total_seconds()))


def _donate_attack(level: int) -> float:
    return sum(spec.get("combat", {}).get("attack", 0.0) for spec in CLAN_DONATE_LEVELS[:level])


async def _chances(session: AsyncSession, clan: Clan, attacking: bool):
    built = await clan_repo.buildings(session, clan.id)
    mods = CombatMods(attack=_donate_attack(clan.donate_level))
    if attacking:
        mods = mods + CombatMods(attack=CLAN_FORGE_ATTACK * built.get(BUILDING_FORGE, 0))
    else:
        walls = built.get(BUILDING_WALL, 0)
        mods = mods + CombatMods(durability=CLAN_WALL_DEFENSE * walls, reduction=CLAN_WALL_DEFENSE * walls / 2)
    return replace(base_chances(), build=BattleBuild(total=mods))


async def targets(session: AsyncSession, user_id: int, page: int) -> tuple[list[WarTarget], int, int]:
    member = await require_member(session, user_id)
    total = max(0, await clan_repo.count_clans(session) - 1)
    pages = max(1, math.ceil(total / CLAN_PAGE))
    page = max(0, min(page, pages - 1))
    rows = await clan_repo.top_page(session, CLAN_PAGE + 1, page * CLAN_PAGE)
    result = [
        WarTarget(c.id, c.name, c.lands, n, shield_left(c) > 0)
        for c, n in rows if c.id != member.clan_id
    ][:CLAN_PAGE]
    return result, page, pages


def _cut_buildings(built: dict[str, int], lands: int) -> dict[str, int]:
    """Какие здания рухнут, если зданий больше, чем земель: по одному с самых многочисленных."""
    lost: dict[str, int] = {}
    counts = dict(built)
    excess = sum(counts.values()) - lands
    while excess > 0:
        kind = max(sorted(counts), key=lambda k: counts[k])
        counts[kind] -= 1
        lost[kind] = lost.get(kind, 0) + 1
        excess -= 1
    return lost


async def attack(session: AsyncSession, redis: Redis, user_id: int, target_id: int, rng: random.Random | None = None) -> WarOutcome:
    member = await require_member(session, user_id, MANAGER_RANKS)
    if target_id == member.clan_id:
        raise ClanError("own_clan")
    lock = await _lock(redis, user_id)
    try:
        locked = {}
        for cid in sorted((member.clan_id, target_id)):
            locked[cid] = await clan_repo.get(session, cid, for_update=True)
        attacker, defender = locked[member.clan_id], locked[target_id]
        if defender is None:
            raise ClanError("clan_gone")
        if cooldown_left(attacker):
            raise ClanError("war_cooldown", cooldown_left(attacker))
        if shield_left(defender):
            raise ClanError("shielded", shield_left(defender))
        a_stacks = await garrison_stacks(session, attacker.id, for_update=True)
        if stacks_power(a_stacks) <= 0:
            raise ClanError("empty_garrison")
        d_stacks = await garrison_stacks(session, defender.id, for_update=True)
        a_power, d_power = stacks_power(a_stacks), stacks_power(d_stacks)
        if d_power > 0:
            result = simulate_battle(
                a_stacks, d_stacks,
                attacker_chances=await _chances(session, attacker, True),
                defender_chances=await _chances(session, defender, False),
                rng=rng,
            )
            await apply_losses(session, attacker.id, result.attacker.dead)
            await apply_losses(session, defender.id, result.defender.dead)
            won, rounds = result.attacker_won, result.rounds
            a_dead, d_dead = result.attacker.total_dead, result.defender.total_dead
        else:
            won, rounds, a_dead, d_dead = True, 0, 0, 0  # пустая рота — сдача без боя

        lands_taken = lands_gained = treasury = 0
        lost: dict[str, int] = {}
        if won:
            ratio = a_power / d_power if d_power > 0 else _NO_ARMY_RATIO
            lands_taken = war_lands(ratio, defender.lands)
            lands_gained = max(0, min(lands_taken, max_lands(attacker) - attacker.lands))
            defender.lands -= lands_taken
            attacker.lands += lands_gained
            treasury = defender.treasury * CLAN_WAR_TREASURY_PERCENT // 100
            defender.treasury -= treasury
            attacker.treasury += treasury
            lost = _cut_buildings(await clan_repo.buildings(session, defender.id), defender.lands)
            for kind, n in lost.items():
                await clan_repo.add_building(session, defender.id, kind, -n)
        now = _now()
        attacker.last_attack_at = now
        defender.shield_until = now + timedelta(hours=CLAN_WAR_SHIELD_HOURS)
        await clan_repo.add_war(
            session, attacker_id=attacker.id, defender_id=defender.id, attacker_name=attacker.name, defender_name=defender.name,
            attacker_won=won, lands_taken=lands_taken, treasury_taken=treasury, attacker_power=a_power, defender_power=d_power,
            attacker_dead=a_dead, defender_dead=d_dead,
        )
        actor = await _name(session, user_id)
        await clan_repo.bump_stats(session, attacker.id, user_id, wars=1, wars_won=int(won), lands_won=lands_gained)
        verdict = "победа" if won else "поражение"
        await clan_repo.log(session, attacker.id, f"⚔️ {actor} напал(а) на «{defender.name}»: {verdict}, земель +{lands_gained}")
        await clan_repo.log(session, defender.id, f"🛡 «{attacker.name}» напал на клан: {'оборона прорвана' if won else 'отбились'}, земель −{lands_taken}")
        outcome = WarOutcome(
            attacker.id, defender.id, attacker.name, defender.name, won, rounds, a_power, d_power, a_dead, d_dead,
            lands_taken, lands_gained, treasury, lost,
            await clan_repo.member_ids(session, attacker.id), await clan_repo.member_ids(session, defender.id),
        )
        await session.commit()
        return outcome
    except Exception:
        await session.rollback()
        raise
    finally:
        await redis.delete(lock)


async def history(session: AsyncSession, clan_id: int):
    return await clan_repo.recent_wars(session, clan_id)


async def my_clan(session: AsyncSession, user_id: int) -> Clan:
    member = await require_member(session, user_id)
    return await clan_repo.get(session, member.clan_id)

