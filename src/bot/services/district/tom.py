"""Бой с Томом Ли — задание цепочки «Преодоление стены» (сервис).

Живёт в домене district рядом с остальными боями (PvE района, бой за город, PvP): движок,
загрузка лагеря, потери — общие. Состояние цепочки (открыт ли Том, отметка победы) —
`services/mastery`. Против Тома у игрока не работают блок выносливости и побег
(raw-notes «Рейды»: «Том Ли игнорирует блок статистов от выносливости, от него не могут
сбежать»). Том — стопка из `TOM_COMBAT_UNITS` «частей» общей мощью `tom_power`, чтобы урон
по нему накапливался по раундам.
"""
from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.absolute import after_battle
from bot.constant.position_skill import VS_BOSS
from bot.services.position_skill.battle import journal, matchup
from bot.constant.cooldown import CD_BATTLE
from bot.services.cooldown import schedule as schedule_ready
from bot.cache.keys import battle_cooldown
from bot.config.game import BATTLE_COOLDOWN_SECONDS
from bot.config.mastery import TOM_COMBAT_UNITS
from bot.constant.extra import CAMP_ATTACK
from bot.db.models.user import User
from bot.services.characteristic import get_combat_profile
from bot.services.combat import CombatStack, base_chances, simulate_battle
from bot.services.district.district import BattleOnCooldownError, NoAttackersError, apply_losses, load_camp
from bot.services.mastery import lock_quest_for_tom, mark_tom_defeated


@dataclass(frozen=True, slots=True)
class TomFightResult:
    won: bool
    stage: int
    rounds: int
    attacker_power: int
    attacker_dead: int
    tom_power: int
    tom_remaining_power: int
    journal: tuple[str, ...] = ()  # журнал боя глазами нападающего (`services/position_skill.journal`)


async def fight_tom(session: AsyncSession, redis: Redis, user: User) -> TomFightResult:
    """Составная операция (правило 10): проверки → КД → бой → потери → (победа) тренер → один
    commit. Порядок блокировок: строка цепочки → стопки лагеря."""
    quest = await lock_quest_for_tom(session, user.id)
    stacks = await load_camp(session, user.id, CAMP_ATTACK, for_update=True)
    if not stacks:
        raise NoAttackersError

    profile = await get_combat_profile(session, user.id)
    key = battle_cooldown(user.id)
    if not await redis.set(key, "1", nx=True, ex=profile.cooldown(BATTLE_COOLDOWN_SECONDS[user.phase], profile.eco.battle_cooldown)):
        raise BattleOnCooldownError(retry_after_seconds=max(0, await redis.ttl(key)))

    tom = [CombatStack(key="tom", unit_power=quest.tom_power / TOM_COMBAT_UNITS, quantity=TOM_COMBAT_UNITS)]
    m = matchup(profile, vs=(VS_BOSS,), defender_chances=base_chances(), attacker_kw={"no_block_no_flee": True}, attacker_stacks=stacks)
    result = simulate_battle(stacks, tom, attacker_chances=m.attacker, defender_chances=m.defender)
    await apply_losses(session, user.id, CAMP_ATTACK, result.attacker.dead)
    abs_lines = await after_battle(session, m, result, attacker_id=user.id, attacker_stacks=stacks)
    if result.attacker_won:
        mark_tom_defeated(quest)
    await session.commit()
    await schedule_ready(redis, user.id, CD_BATTLE, await redis.ttl(key))
    return TomFightResult(
        journal=journal(result, m.spy) + abs_lines,
        won=result.attacker_won,
        stage=quest.stage,
        rounds=result.rounds,
        attacker_power=result.attacker.initial_power,
        attacker_dead=result.attacker.total_dead,
        tom_power=quest.tom_power,
        tom_remaining_power=result.defender.remaining_power,
    )
