"""Предвидение — прогноз боя до боя (сервис).

Пользователь 2026-10-02: путь Предвидения «позволяет оценить результаты сражения до этого
сражения». Уровень предвидения (`EconomyMods.foresight`: путь Предвидения, гении наблюдения
и тактики) задаёт точность: 1 — шанс победы грубо (до 10%), 2 — плюс ожидаемые потери,
3 — точный прогноз (больше симуляций, до 1%). Считается тем же движком, что и бой, по
текущим армиям — без записи в БД.
"""
from __future__ import annotations

from dataclasses import dataclass
from random import Random

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.characteristic import extra_power_for_rank
from bot.config.unique_path import FORESIGHT_SIMULATIONS
from bot.constant.extra import CAMP_ATTACK
from bot.services.characteristic import get_combat_profile
from bot.services.combat import CombatChances, CombatStack, base_chances, simulate_battle
from bot.services.district.army import load_camp
from bot.services.district.boss import boss_army, boss_chances


@dataclass(frozen=True, slots=True)
class Forecast:
    level: int
    win_rate: float  # 0..1
    loss_share: float  # доля своей армии, которая погибнет (в среднем)


def _simulate(attacker, a_chances: CombatChances, defender, d_chances: CombatChances, level: int) -> Forecast:
    runs = FORESIGHT_SIMULATIONS[min(level, 3)]
    wins, lost = 0, 0.0
    quantity = sum(s.quantity for s in attacker) or 1
    for seed in range(runs):
        result = simulate_battle(attacker, defender, attacker_chances=a_chances, defender_chances=d_chances, rng=Random(seed))
        wins += result.attacker_won
        lost += result.attacker.total_dead / quantity
    return Forecast(level=level, win_rate=wins / runs, loss_share=lost / runs)


async def _me(session: AsyncSession, user_id: int):
    profile = await get_combat_profile(session, user_id)
    if not profile.eco.foresight:
        return None, None, 0
    stacks = await load_camp(session, user_id, CAMP_ATTACK, for_update=False)
    return stacks, profile, profile.eco.foresight


async def vs_bots(session: AsyncSession, user_id: int, rank: str, quantity: int) -> Forecast | None:
    stacks, profile, level = await _me(session, user_id)
    if not level or not stacks:
        return None
    bots = [CombatStack(key="bot", unit_power=extra_power_for_rank(rank), quantity=quantity)]
    return _simulate(stacks, profile.chances(), bots, base_chances(), level)


async def vs_player(session: AsyncSession, user_id: int, defender_id: int) -> Forecast | None:
    """Против лагеря атаки другого игрока (бой при принятии вызова)."""
    stacks, profile, level = await _me(session, user_id)
    if not level or not stacks:
        return None
    defender = await load_camp(session, defender_id, CAMP_ATTACK, for_update=False)
    if not defender:
        return Forecast(level=level, win_rate=1.0, loss_share=0.0)
    d_profile = await get_combat_profile(session, defender_id)
    return _simulate(stacks, profile.chances(), defender, d_profile.chances(), level)


async def vs_boss(session: AsyncSession, user_id: int, code: str, phase: str) -> Forecast | None:
    stacks, profile, level = await _me(session, user_id)
    if not level or not stacks:
        return None
    boss, _ = boss_army(code, stacks, phase)
    return _simulate(stacks, profile.chances(), boss, boss_chances(code), level)
