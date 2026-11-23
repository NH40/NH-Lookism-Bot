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

KIND_BOSS, KIND_CITY, KIND_RAID, KIND_WAR, KIND_TOM = "boss", "city", "raid", "war", "tom"


async def _create_pve(session, redis, user, kind: str, stacks, enemy, m, enemy_name: str, meta: dict, auto: bool) -> dict:
    from bot.services.arena.sources import energy_for, perks_for

    return await core.create(
        redis, session=session, kind=kind, a_uid=user.id, d_uid=None, a_stacks=stacks, d_stacks=enemy, a_chances=m.attacker, d_chances=m.defender,
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
        redis, session=session, kind=KIND_WAR, a_uid=a_id, d_uid=d_id, a_stacks=stacks_a, d_stacks=stacks_d, a_chances=m.attacker, d_chances=m.defender,
        a_perks=await perks_for(session, a_id), d_perks=await perks_for(session, d_id), a_auto=False, d_auto=False,
        a_name=await _label(session, a_id), d_name=await _label(session, d_id), meta={"war_id": war_id},
        a_energy=await energy_for(session, a_id), d_energy=await energy_for(session, d_id),
    )
    await session.commit()
    await _notify(a_id, "⚔️ <b>Император принял войну — бой вождей начался!</b>\n\nЖми «Войти в бой». Не зайдёшь — за тебя ходит автоатака.", st["id"])
    return st


async def start_war_expired(session: AsyncSession, redis: Redis, war_id: int) -> bool:
    """Защитник не принял войну — бой всё равно онлайн: нападающий ходит сам, за защитника автоатака лагерем защиты
    (он может зайти и выключить её). False — нельзя (кто-то уже в бою, пустой лагерь) → прежний автобой."""
    from bot.constant.empire import WAR_FORFEIT
    from bot.db.repositories import empire as empire_repo
    from bot.services.arena.sources import energy_for, perks_for
    from bot.services.empire.war import _label, war_fight

    war = await empire_repo.get_pending_for_update(session, war_id)
    if war is None:
        return False
    for uid in (war.attacker_id, war.defender_id):
        if await core.current_of(redis, uid):
            return False
    stacks_a, stacks_d, m = await war_fight(session, war, accepted=False)
    if not stacks_a or not stacks_d:
        return False
    a_id, d_id = war.attacker_id, war.defender_id
    war.expires_at = datetime.now(timezone.utc) + timedelta(seconds=ARENA_TTL_SECONDS)  # не заберёт как неявку повторно
    a_name, d_name = await _label(session, a_id), await _label(session, d_id)
    st = await core.create(
        redis, session=session, kind=KIND_WAR, a_uid=a_id, d_uid=d_id, a_stacks=stacks_a, d_stacks=stacks_d, a_chances=m.attacker, d_chances=m.defender,
        a_perks=await perks_for(session, a_id), d_perks=await perks_for(session, d_id), a_auto=False, d_auto=True,
        a_name=a_name, d_name=f"{d_name} (оборона)", meta={"war_id": war_id, "resolution": WAR_FORFEIT},
        a_energy=await energy_for(session, a_id), d_energy=await energy_for(session, d_id),
    )
    await session.commit()
    await _notify(a_id, f"⚔️ <b>{d_name} не принял войну — бой с его обороной идёт онлайн!</b>\n\n"
                        "Жми «Войти в бой». Не зайдёшь — за тебя ходит автоатака.", st["id"])
    await _notify(d_id, f"🚨 <b>{a_name} напал на твою империю!</b> Ты не принял войну — бьётся лагерь защиты на автоатаке.\n\n"
                        "Зайди в бой и веди его сам: перки, мини-игры.", st["id"])
    return True


async def _finish_war(redis: Redis, st: dict, result) -> None:
    from bot.constant.empire import WAR_ACCEPTED
    from bot.services.empire.war import settle_war_online

    async with _SF["sf"]() as session:
        o = await settle_war_online(session, redis, st["meta"]["war_id"], result, st["meta"].get("resolution") or WAR_ACCEPTED)
    won = bool(o and o.attacker_won)
    st["report"] = {"won": won}
    await core.save(redis, st)
    await _notify(st["a"]["uid"], f"🏁 Война вождей: {'победа' if won else 'поражение'}.")
    await _notify(st["d"]["uid"], f"🏁 Война вождей: {'поражение' if won else 'победа'}.")


# --- Том Ли: финал этапа мастерства после 4 мини-игр (2026-11-23) ---


def _tom_army(quest):
    from bot.config.mastery import TOM_COMBAT_UNITS
    from bot.services.combat import CombatStack

    return [CombatStack(key="tom", unit_power=quest.tom_power / TOM_COMBAT_UNITS, quantity=TOM_COMBAT_UNITS)]


def _tom_matchup(profile, stacks):
    from bot.constant.position_skill import VS_BOSS
    from bot.services.combat import base_chances
    from bot.services.position_skill.battle import matchup

    return matchup(profile, vs=(VS_BOSS,), defender_chances=base_chances(), attacker_kw={"no_block_no_flee": True}, attacker_stacks=stacks)


async def start_tom(session: AsyncSession, redis: Redis, user, *, auto: bool = False) -> dict:
    """Онлайн-бой с Томом Ли: те же проверки и КД, что у прежнего `fight_tom`; Том — 80/100/120% мощи лагеря атаки."""
    from bot.cache.keys import battle_cooldown
    from bot.constant.cooldown import CD_BATTLE
    from bot.constant.extra import CAMP_ATTACK
    from bot.services.admin.live_config import battle_cooldown_seconds
    from bot.services.characteristic import get_combat_profile
    from bot.services.cooldown import schedule as schedule_ready
    from bot.services.country import ensure_battles_open
    from bot.services.district.district import BattleOnCooldownError, NoAttackersError, load_camp
    from bot.services.mastery import lock_quest_for_tom

    if await core.current_of(redis, user.id):
        raise core.ArenaError("in_battle")
    await ensure_battles_open(session, user.country_code)
    quest = await lock_quest_for_tom(session, user.id)
    stacks = await load_camp(session, user.id, CAMP_ATTACK, for_update=True)
    if not stacks:
        raise NoAttackersError
    profile = await get_combat_profile(session, user.id)
    key = battle_cooldown(user.id)
    if not await redis.set(key, "1", nx=True, ex=profile.cooldown(battle_cooldown_seconds(user.phase), profile.eco.battle_cooldown)):
        raise BattleOnCooldownError(retry_after_seconds=max(0, await redis.ttl(key)))
    st = await _create_pve(session, redis, user, KIND_TOM, stacks, _tom_army(quest), _tom_matchup(profile, stacks),
                           "🥋 Том Ли", {"stage": quest.stage}, auto)
    await session.rollback()  # бой идёт без открытой транзакции
    await schedule_ready(redis, user.id, CD_BATTLE, await redis.ttl(key))
    return st


async def _finish_tom(redis: Redis, st: dict, result) -> None:
    from bot.constant.extra import CAMP_ATTACK
    from bot.constant.ledger import BATTLE_TOM
    from bot.db.models.user import User
    from bot.db.repositories import mastery as mastery_repo
    from bot.services.absolute import after_battle
    from bot.services.characteristic import get_combat_profile
    from bot.services.district.district import apply_losses, load_camp
    from bot.services.mastery import games_ready, mark_tom_defeated

    async with _SF["sf"]() as session:
        user = await session.get(User, st["a"]["uid"])
        quest = await mastery_repo.get(session, user.id, for_update=True)
        stacks = await load_camp(session, user.id, CAMP_ATTACK, for_update=True)
        m = _tom_matchup(await get_combat_profile(session, user.id), stacks)
        await apply_losses(session, user.id, CAMP_ATTACK, result.attacker.dead)
        await after_battle(session, m, result, kind=BATTLE_TOM, attacker_id=user.id, attacker_stacks=stacks)
        # этап мог смениться (админ) — засчитываем победу только тому этапу, за который бились
        won = bool(result.attacker_won and quest is not None and quest.stage == st["meta"].get("stage") and games_ready(quest))
        if won:
            mark_tom_defeated(quest)
        await session.commit()
    st["report"] = {"won": bool(result.attacker_won), "stage_closed": won}
    await core.save(redis, st)
    await _notify(st["a"]["uid"], "🏁 Том Ли побеждён — этап мастерства закрыт!" if won else "🏁 Том Ли устоял. Подготовься и попробуй снова.")


# --- обучение (2026-11-23) ---

KIND_TUTORIAL = "tutorial"


async def start_tutorial(session: AsyncSession, redis: Redis, user, city: int, district: int | None) -> dict:
    """Бой на учебной карте онлайн — с первого боя новичок видит перки и журнал «откуда что»."""
    from bot.config.tutorial.tutorial import TRAINING_CITIES
    from bot.services.tutorial.tutorial import prepare_attack

    if await core.current_of(redis, user.id):
        raise core.ArenaError("in_battle")
    stacks, defender, m, targets = await prepare_attack(session, redis, user.id, city, district)
    st = await _create_pve(session, redis, user, KIND_TUTORIAL, stacks, defender, m, f"Боты: {TRAINING_CITIES[city].name}",
                           {"city": city, "targets": targets}, False)
    await session.rollback()
    return st


async def _finish_tutorial(redis: Redis, st: dict, result) -> None:
    from bot.handlers.tutorial.tutorial import advance_text
    from bot.services.tutorial.tutorial import settle_attack
    from bot.texts.tutorial import FIGHT_LOST, FIGHT_WON
    from bot.utils.formatting import format_number

    async with _SF["sf"]() as session:
        report, adv = await settle_attack(session, st["a"]["uid"], st["meta"]["city"], st["meta"]["targets"], result)
    st["report"] = {"won": report.won, "captured": report.captured}
    await core.save(redis, st)
    msg = (FIGHT_WON if report.won else FIGHT_LOST).format(
        city=report.city, captured=report.captured, dead=format_number(report.dead), attackers=format_number(report.attackers))
    await _notify(st["a"]["uid"], "🎓 " + msg + ("\n\n" + advance_text(adv) if advance_text(adv) else ""))


core.register_finisher(KIND_BOSS, _finish_boss)
core.register_finisher(KIND_CITY, _finish_city)
core.register_finisher(KIND_RAID, _finish_raid)
core.register_finisher(KIND_WAR, _finish_war)
core.register_finisher(KIND_TOM, _finish_tom)
core.register_finisher(KIND_TUTORIAL, _finish_tutorial)
