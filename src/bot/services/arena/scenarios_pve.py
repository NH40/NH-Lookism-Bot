"""Сценарии онлайн-боя, часть 2 (2026-11-20): босс, город (круг против ботов), рейд, война императоров.

Тот же принцип, что в `scenarios`: подготовка — общей функцией автобоя, итог — её же `settle_*`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.arena import ARENA_TTL_SECONDS
from bot.services.arena import arena as core
from bot.services.arena.scenarios import _SF, _name, _notify

KIND_BOSS, KIND_CITY, KIND_RAID, KIND_WAR = "boss", "city", "raid", "war"


async def _create_pve(session, redis, user, kind: str, stacks, enemy, m, enemy_name: str, meta: dict, auto: bool) -> dict:
    from bot.services.arena.sources import energy_for, perks_for

    return await core.create(
        redis, kind=kind, a_uid=user.id, d_uid=None, a_stacks=stacks, d_stacks=enemy, a_chances=m.attacker, d_chances=m.defender,
        a_perks=await perks_for(session, user.id), d_perks=[], a_auto=auto, d_auto=True, a_name=await _name(session, user.id),
        d_name=enemy_name, meta=meta, a_energy=await energy_for(session, user.id),
    )


async def _free(redis: Redis, *user_ids: int) -> None:
    for uid in user_ids:
        if await core.current_of(redis, uid):
            raise core.ArenaError("in_battle")


# --- босс ---

async def start_boss(session: AsyncSession, redis: Redis, user, event_id: int, *, auto: bool = False) -> dict:
    from bot.services.district.boss import prepare_boss
    from bot.texts.event import BOSS_NAMES

    await _free(redis, user.id)
    prep = await prepare_boss(session, redis, user, event_id)
    st = await _create_pve(session, redis, user, KIND_BOSS, prep.stacks, prep.boss, prep.matchup,
                           BOSS_NAMES.get(prep.event.code, "Босс"), {"event_id": event_id}, auto)
    await session.rollback()
    return st


async def _finish_boss(redis: Redis, st: dict, result) -> None:
    from bot.db.models.user import User
    from bot.services.district.boss import prepare_boss, settle_boss

    async with _SF["sf"]() as session:
        user = await session.get(User, st["a"]["uid"])
        prep = await prepare_boss(session, redis, user, st["meta"]["event_id"], rebuild=True)
        rep = await settle_boss(session, user, prep, result)
    st["report"] = {"won": rep.won, "fragments": rep.fragments, "fragment_kind": rep.fragment_kind}
    await core.save(redis, st)


# --- город (круг против ботов города) ---

async def start_city(session: AsyncSession, redis: Redis, user, city_id: int, *, auto: bool = False) -> dict:
    from bot.services.district.city import prepare_city_bots

    await _free(redis, user.id)
    prep = await prepare_city_bots(session, redis, user, city_id)
    st = await _create_pve(session, redis, user, KIND_CITY, prep.stacks, prep.defender, prep.matchup,
                           f"Боты города {prep.city.name}", {"city_id": city_id}, auto)
    await session.rollback()
    return st


async def _finish_city(redis: Redis, st: dict, result) -> None:
    from bot.db.models.user import User
    from bot.services.district.city import prepare_city_bots, settle_city_bots

    async with _SF["sf"]() as session:
        user = await session.get(User, st["a"]["uid"])
        prep = await prepare_city_bots(session, redis, user, st["meta"]["city_id"], rebuild=True)
        rep = await settle_city_bots(session, redis, user, prep, result)
    st["report"] = {"won": rep.won, "captured": rep.captured, "city": rep.city_name, "promoted_to": rep.promoted_to}
    await core.save(redis, st)


# --- рейд ---

async def start_raid(session: AsyncSession, redis: Redis, user, *, auto: bool = False) -> dict:
    """Встретить свой рейд лагерем атаки онлайн. Срок рейда сдвигается на время боя — фоновый проход его не тронет."""
    from bot.constant.extra import CAMP_ATTACK
    from bot.constant.position_skill import VS_DISTRICT
    from bot.services.characteristic import get_combat_profile
    from bot.services.combat import base_chances
    from bot.services.district.army import load_camp
    from bot.services.position_skill.battle import matchup
    from bot.services.raid.raid import RaidError, pending_of, raid_enemy

    await _free(redis, user.id)
    raid = await pending_of(session, user.id)
    if raid is None:
        raise RaidError("no_raid")
    stacks = await load_camp(session, user.id, CAMP_ATTACK, for_update=True)
    if not stacks:
        raise core.ArenaError("no_army")
    m = matchup(await get_combat_profile(session, user.id), vs=(VS_DISTRICT,), defender_chances=base_chances(), attacker_stacks=stacks)
    raid.starts_at = datetime.now(timezone.utc) + timedelta(seconds=ARENA_TTL_SECONDS)
    st = await _create_pve(session, redis, user, KIND_RAID, stacks, raid_enemy(raid), m, "Рейд", {"raid_id": raid.id}, auto)
    await session.commit()
    return st


async def _finish_raid(redis: Redis, st: dict, result) -> None:
    from bot.services.raid.raid import settle_online

    async with _SF["sf"]() as session:
        o = await settle_online(session, st["meta"]["raid_id"], result)
    st["report"] = {"won": bool(o and o.won), "rewards": o.rewards if o else {}, "lost": o.districts_lost if o else 0}
    await core.save(redis, st)


# --- война императоров: вождь против вождя ---

async def start_war(session: AsyncSession, redis: Redis, defender_id: int, war_id: int):
    """Защитник принимает войну онлайн. Просрочена — как раньше, автобой (→ `WarOutcome`)."""
    from bot.db.repositories import empire as empire_repo
    from bot.services.arena.sources import energy_for, perks_for
    from bot.services.empire.war import WarNotFoundError, _label, accept_war, war_fight

    war = await empire_repo.get_pending_for_update(session, war_id)
    if war is None or war.defender_id != defender_id:
        raise WarNotFoundError
    if datetime.now(timezone.utc) >= war.expires_at:
        return await accept_war(session, redis, defender_id, war_id)
    await _free(redis, war.attacker_id, war.defender_id)
    stacks_a, stacks_d, m = await war_fight(session, war)
    a_id, d_id = war.attacker_id, war.defender_id
    war.expires_at = datetime.now(timezone.utc) + timedelta(seconds=ARENA_TTL_SECONDS)  # не заберёт как неявку
    st = await core.create(
        redis, kind=KIND_WAR, a_uid=a_id, d_uid=d_id, a_stacks=stacks_a, d_stacks=stacks_d, a_chances=m.attacker, d_chances=m.defender,
        a_perks=await perks_for(session, a_id), d_perks=await perks_for(session, d_id), a_auto=False, d_auto=False,
        a_name=await _label(session, a_id), d_name=await _label(session, d_id), meta={"war_id": war_id},
        a_energy=await energy_for(session, a_id), d_energy=await energy_for(session, d_id),
    )
    await session.commit()
    await _notify(a_id, "⚔️ <b>Император принял войну — бой вождей начался!</b>\n\nЖми «Войти в бой». Не зайдёшь — за тебя ходит автоатака.", st["id"])
    return st


async def _finish_war(redis: Redis, st: dict, result) -> None:
    from bot.services.empire.war import settle_war_online

    async with _SF["sf"]() as session:
        o = await settle_war_online(session, redis, st["meta"]["war_id"], result)
    won = bool(o and o.attacker_won)
    st["report"] = {"won": won}
    await core.save(redis, st)
    await _notify(st["a"]["uid"], f"🏁 Война вождей: {'победа' if won else 'поражение'}.")
    await _notify(st["d"]["uid"], f"🏁 Война вождей: {'поражение' if won else 'победа'}.")


core.register_finisher(KIND_BOSS, _finish_boss)
core.register_finisher(KIND_CITY, _finish_city)
core.register_finisher(KIND_RAID, _finish_raid)
core.register_finisher(KIND_WAR, _finish_war)
