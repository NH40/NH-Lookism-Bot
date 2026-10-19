"""Бой с боссом события на карте — Ким Гапрен, Джинен, Элита (сервис).

Пользователь 2026-10-02 (`docs/design/development_systems.md`, «Боссы на карте»): с Ким
Гапрена падают фрагменты пути, с Джинена — фрагменты уникальных техник, с Элиты — фрагменты
гениальности. Решения автора кода: у каждого игрока свой бой (как с Томом Ли), мощь босса —
доля мощи его лагеря атаки, способности — из описания рейдов (raw-notes «Рейды»):
- Ким Гапрен растёт после каждого убитого статиста — против него сильные бойцы;
- Джинен лечится, когда его бьют слабые — только сильные статисты;
- Элита — от его атак не увернуться, ловкость бесполезна.

Одна победа над боссом на событие (`map_event_entries.won`, `FOR UPDATE`), попытки —
сколько угодно в пределах КД боя с боссом — своего, отдельного от КД сражений за
районы (`cache/keys.boss_cooldown`, длительность та же, по фазе). Капель крови боссы
не дают (пользователь 2026-10-03: капли — только за пробуждение и активную игру за патч).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, replace

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.admin.live_config import battle_cooldown_seconds
from bot.services.absolute import after_battle
from bot.constant.position_skill import VS_BOSS
from bot.services.position_skill.battle import journal, matchup
from bot.cache.keys import boss_cooldown
from bot.config.event import (
    BOSS_FRAGMENTS,
    BOSS_MODS,
    BOSS_POWER_MIN,
    BOSS_POWER_PERCENT,
    BOSS_UNIT_FLOOR_RANK,
)
from bot.config.characteristic import extra_unit_power
from bot.constant.event import BOSS_FRAGMENT, EVENT_BOSS
from bot.constant.extra import CAMP_ATTACK
from bot.db.models.user import User
from bot.db.repositories import event as event_repo
from bot.constant.activity import ACT_BATTLE
from bot.constant.dev_quest import TASK_BOSS_WIN, TASK_WIN_PVE
from bot.constant.phase import PHASE_FIST
from bot.services.dev_quest import emit as quest_event
from bot.services.activity import log as log_activity
from bot.texts.activity import LOG_BOSS, LOST, WON
from bot.texts.event import BOSS_NAMES
from bot.services.characteristic import get_combat_profile
from bot.services.combat import BattleBuild, CombatChances, CombatMods, CombatStack, base_chances, simulate_battle
from bot.services.district.army import apply_losses, load_camp
from bot.services.district.district import BattleOnCooldownError, NoAttackersError


class EventGoneError(Exception):
    """События уже нет на карте (или это не босс)."""


class BossAlreadyDefeatedError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class BossFightResult:
    won: bool
    boss: str
    rounds: int
    attacker_power: int
    attacker_dead: int
    boss_power: int
    boss_remaining_power: int
    fragment_kind: str
    fragments: int = 0
    journal: tuple[str, ...] = ()  # журнал боя глазами нападающего (`services/position_skill.journal`)


def boss_army(code: str, stacks: list[CombatStack], phase: str) -> tuple[list[CombatStack], int]:
    """Армия босса от лагеря атаки игрока: общая мощь — `BOSS_POWER_PERCENT`, единица —
    как самый сильный боец игрока, но не слабее порога фазы (`BOSS_UNIT_FLOOR_RANK`). Так
    способности работают по смыслу: толпа слабых кормит Гапрена и лечит Джинена, немногие
    сильные — нет."""
    power = sum(s.unit_power * s.quantity for s in stacks)
    boss_power = max(BOSS_POWER_MIN, int(power * BOSS_POWER_PERCENT[code] / 100))
    floor = extra_unit_power(BOSS_UNIT_FLOOR_RANK[phase], 0, 0)
    unit = max(floor, max((s.unit_power for s in stacks), default=floor))
    units = max(1, round(boss_power / unit))
    return [CombatStack(key=("boss", code), unit_power=boss_power / units, quantity=units)], boss_power


def boss_chances(code: str) -> CombatChances:
    """Базовые реакции + способности босса (`BOSS_MODS`)."""
    return replace(base_chances(), build=BattleBuild(total=CombatMods.of(BOSS_MODS[code])))


async def fight_boss(
    session: AsyncSession, redis: Redis, user: User, event_id: int, rng: random.Random | None = None
) -> BossFightResult:
    """Составная операция (правило 10): событие живо → участие под `FOR UPDATE` → лагерь →
    КД → бой → потери → (победа) награда → один commit."""
    rng = rng or random.Random()
    event = await event_repo.get_active(session, event_id, user.id)
    if event is None or event.kind != EVENT_BOSS:
        raise EventGoneError
    entry = await event_repo.lock_entry(session, event_id, user.id)
    if entry.won:
        raise BossAlreadyDefeatedError
    stacks = await load_camp(session, user.id, CAMP_ATTACK, for_update=True)
    if not stacks:
        raise NoAttackersError

    profile = await get_combat_profile(session, user.id)
    key = boss_cooldown(user.id)
    if not await redis.set(key, "1", nx=True, ex=profile.cooldown(battle_cooldown_seconds(user.phase), profile.eco.battle_cooldown)):
        raise BattleOnCooldownError(retry_after_seconds=max(0, await redis.ttl(key)))

    boss, boss_power = boss_army(event.code, stacks, user.phase)
    m = matchup(profile, vs=(VS_BOSS,), defender_chances=boss_chances(event.code), attacker_stacks=stacks, rng=rng)
    result = simulate_battle(stacks, boss, attacker_chances=m.attacker, defender_chances=m.defender, rng=rng)
    await apply_losses(session, user.id, CAMP_ATTACK, result.attacker.dead)
    abs_lines = await after_battle(session, m, result, attacker_id=user.id, attacker_stacks=stacks)
    entry.attempts += 1

    fragment_kind = BOSS_FRAGMENT[event.code]
    fragments = 0
    if result.attacker_won:
        entry.won = True
        await quest_event(session, user.id, TASK_BOSS_WIN)
        if user.phase == PHASE_FIST:
            # Аналог для императора (пользователь 2026-10-12): бот-районов у него нет — победа над
            # боссом засчитывается и заданиям «победить ботов района или города».
            await quest_event(session, user.id, TASK_WIN_PVE)
        lo, hi = BOSS_FRAGMENTS[user.phase]
        fragments = round(rng.randint(lo, hi) * (1 + profile.eco.fragment_bonus))
        await event_repo.grant_currency(session, user.id, fragment_kind, fragments)
    await log_activity(
        session, user.id, ACT_BATTLE, LOG_BOSS.format(name=BOSS_NAMES[event.code], outcome=WON if result.attacker_won else LOST)
    )
    await session.commit()
    return BossFightResult(
        journal=journal(result, m.spy) + abs_lines,
        won=result.attacker_won,
        boss=event.code,
        rounds=result.rounds,
        attacker_power=result.attacker.initial_power,
        attacker_dead=result.attacker.total_dead,
        boss_power=boss_power,
        boss_remaining_power=result.defender.remaining_power,
        fragment_kind=fragment_kind,
        fragments=fragments,
    )
