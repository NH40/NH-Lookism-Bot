"""Характеристики и мастерство игрока в бою и в КД (сервис).

raw-notes «Сражения» + пользователь 2026-09-30 («считай самостоятельно, чтобы подходило по
балансу»; Выносливость «поглощает часть урона и даёт множитель к блокам отряда»). Числа —
`config/characteristic`:

- Ловкость → уклонение (+п.п. за ранг) и шанс «второй атаки без КД» (+1% за ранг);
- Скорость → побег (+п.п. за ранг) и −1% времени противнику на принятие вызова за ранг;
- Выносливость → поглощение доли урона и множитель к шансу блока;
- Сила → +1% мощи армии за ранг; мастерство Силы +10/25/50%;
- мастерство Техники ×1/5/10 к бонусам характеристик к шансам (уклонение, побег, блок);
- мастерство Выносливости спасает 10/20/30% погибших; мастерство Скорости −10/20/30% ко
  всем КД.

Шансы режутся потолками (`REACTION_MAX` на реакцию, `REACTIONS_TOTAL_MAX` на сумму), иначе
армии двух прокачанных игроков стали бы почти бессмертными.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, replace

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.absolute import KUROPATKA_REVIVE, OGURCHIK_ATTACK, OGURCHIK_REACTIONS, TABASKO_SUPPRESS
from bot.constant.absolute import ABS_KUROPATKA, ABS_NIKITA, ABS_OGURCHIK, ABS_TABASKO
from bot.services.combat.mods import CombatMods
from bot.config.characteristic import (
    AGILITY_DODGE_PP_PER_RANK,
    AGILITY_FREE_ATTACK_PERCENT_PER_RANK,
    ENDURANCE_ABSORB_PERCENT_PER_RANK,
    ENDURANCE_BLOCK_MULT_PERCENT_PER_RANK,
    REACTION_MAX,
    REACTIONS_TOTAL_MAX,
    SPEED_ACCEPT_WINDOW_PERCENT_PER_RANK,
    SPEED_FLEE_PP_PER_RANK,
    STRENGTH_POWER_PERCENT_PER_RANK,
    endurance_mastery_loss_save_percent,
    speed_mastery_cd_reduction_percent,
    strength_mastery_power_percent,
    technique_mastery_multiplier,
)
from bot.constant.characteristic import (
    MASTERY_ENDURANCE,
    MASTERY_SPEED,
    MASTERY_STRENGTH,
    MASTERY_TECHNIQUE,
    STAT_AGILITY,
    STAT_ENDURANCE,
    STAT_SPEED,
    STAT_STRENGTH,
)
from bot.db.repositories import characteristic as char_repo
from bot.services.build import EMPTY_BUILD, Build, EconomyMods, capped, get_build
from bot.constant.build import SOURCE_BLOODLINE, SOURCE_GENIUS, SOURCE_PATH, SOURCE_TECHNIQUE
from bot.constant.position_skill import ROLE_DEFENSE
from bot.services.combat import CombatChances, base_chances
from bot.services.position_skill.position_skill import NO_EFFECTS, SpyOutcome

COPY_ALL_SOURCES = (SOURCE_PATH, SOURCE_TECHNIQUE, SOURCE_BLOODLINE, SOURCE_GENIUS)


def absolute_mods(absolutes: frozenset[str]) -> CombatMods:
    """Боевые перки абсолютов: Куропатка (воскрешение павших), Табаско (реакции врага
    срываются), Огурчик («плюс вайбик»)."""
    mods = CombatMods()
    if ABS_KUROPATKA in absolutes:
        mods = mods + CombatMods(loss_save=KUROPATKA_REVIVE)
    if ABS_TABASKO in absolutes:
        mods = mods + CombatMods(suppress=TABASKO_SUPPRESS)
    if ABS_OGURCHIK in absolutes:
        r = OGURCHIK_REACTIONS
        mods = mods + CombatMods(attack=OGURCHIK_ATTACK, dodge=r, block=r, counter=r, flee=r)
    return mods


@dataclass(frozen=True, slots=True)
class CombatProfile:
    ranks: dict[str, int]
    mastery: dict[str, int]
    # Бафы систем развития (родословная, путь, УТ, гениальность × пробуждение) — в бой
    # уходят через `chances().build`, небоевые — через `eco` (`services/build`).
    build: Build = EMPTY_BUILD

    @property
    def eco(self) -> EconomyMods:
        return self.build.eco

    @property
    def power_percent(self) -> float:
        """Множитель мощи армии в процентах: 100 + Сила (+1%/ранг) + мастерство Силы + мощь
        армии от систем развития (родословная Муджина, `army_power`)."""
        return (
            100
            + self.ranks[STAT_STRENGTH] * STRENGTH_POWER_PERCENT_PER_RANK
            + strength_mastery_power_percent(self.mastery[MASTERY_STRENGTH])
            + self.eco.army_power * 100
        )

    def chances(
        self,
        *,
        no_block_no_flee: bool = False,
        role: str | None = None,
        vs: tuple[str, ...] = (),
        spy_cast: SpyOutcome | None = None,
        spy_taken: SpyOutcome | None = None,
        no_absolutes: bool = False,
    ) -> CombatChances:
        """Шансы реакций армии игрока. `no_block_no_flee` — бой против Тома Ли (его
        способность: блок выносливости и побег не работают). `role`/`vs` — контекст боя для
        навыков позиций (`constant/position_skill`): нападение/защита и тип цели. `spy_cast` —
        шпион этой стороны (бафы, раундовые дебафы цели), `spy_taken` — шпион противника по
        этой стороне (отключённые позиции, дебафы, не вышедшие на бой, снятые зелья)."""
        base = base_chances()
        tech = technique_mastery_multiplier(self.mastery[MASTERY_TECHNIQUE])
        dodge = base.dodge + self.ranks[STAT_AGILITY] * AGILITY_DODGE_PP_PER_RANK / 100 * tech
        flee = base.flee + self.ranks[STAT_SPEED] * SPEED_FLEE_PP_PER_RANK / 100 * tech
        block = base.block * (1 + self.ranks[STAT_ENDURANCE] * ENDURANCE_BLOCK_MULT_PERCENT_PER_RANK / 100 * tech)
        counter = base.counter
        if no_block_no_flee:
            block = flee = 0.0
        reactions = [min(REACTION_MAX, x) for x in (dodge, block, counter, flee)]
        total = sum(reactions)
        if total > REACTIONS_TOTAL_MAX:
            reactions = [x * REACTIONS_TOTAL_MAX / total for x in reactions]
        dodge, block, counter, flee = reactions
        return CombatChances(
            dodge=dodge,
            block=block,
            counter=counter,
            flee=flee,
            loss_save=endurance_mastery_loss_save_percent(self.mastery[MASTERY_ENDURANCE]) / 100,
            absorb=self.ranks[STAT_ENDURANCE] * ENDURANCE_ABSORB_PERCENT_PER_RANK / 100,
            **self._position_parts(role, vs, spy_cast, spy_taken, no_absolutes),
        )

    def _position_parts(self, role, vs, spy_cast, spy_taken, no_absolutes=False) -> dict:
        """Навыки позиций и шпионы → поля `CombatChances` (build, дебафы, триггеры, …)."""
        positions = self.build.positions or NO_EFFECTS
        if spy_taken is not None and spy_taken.disable:
            positions = positions.without(spy_taken.disable)
        battle = self.build.battle
        total = battle.total + positions.combat(role, vs)
        triggers = positions.triggers_for(role)
        if spy_cast is not None:
            total = total + spy_cast.attacker_mods
            triggers = triggers + spy_cast.triggers
        if spy_taken is not None:
            total = total + spy_taken.enemy_mods
            if spy_taken.special.get("disable_potions"):
                total = total + self.build.potion_combat.scale(-1)
        absolutes = frozenset() if no_absolutes else self.build.absolutes
        total = total + absolute_mods(absolutes)
        copy = positions.get("copy")
        if copy:  # «Адаптация»: копирует долю всех боевых источников противника
            battle = replace(
                battle,
                copy_sources=tuple(dict.fromkeys(battle.copy_sources + COPY_ALL_SOURCES)),
                copy_strength=battle.copy_strength + copy,
            )
        return {
            "build": battle.with_total(total),
            "enemy_mods": positions.enemy,
            "triggers": triggers,
            "withheld": spy_taken.withheld if spy_taken is not None else 0.0,
            "loss_cap": positions.get("def_loss_cap") if role == ROLE_DEFENSE else 0.0,
            "despair_strike": ABS_NIKITA in absolutes,
        }

    def cooldown(self, seconds: int, bonus: float = 0.0) -> int:
        """Любой КД игрока с мастерством Скорости (−10/20/30%) и, если передано, сокращением
        этого КД от систем развития (`bonus` — доля из `eco`, режется `capped`)."""
        reduction = speed_mastery_cd_reduction_percent(self.mastery[MASTERY_SPEED]) / 100 + capped(bonus, 0.6)
        return max(1, round(seconds * (1 - min(0.9, reduction))))

    def accept_window(self, seconds: int) -> int:
        """Время противнику на принятие вызова этого игрока: −1% за ранг Скорости."""
        return max(60, round(seconds * (100 - self.ranks[STAT_SPEED] * SPEED_ACCEPT_WINDOW_PERCENT_PER_RANK) / 100))

    def free_attack_percent(self) -> int:
        """Шанс «второй атаки без КД» (Ловкость, +1% за ранг)."""
        return self.ranks[STAT_AGILITY] * AGILITY_FREE_ATTACK_PERCENT_PER_RANK

    def rolls_free_attack(self, rng: random.Random | None = None) -> bool:
        return (rng or random).random() * 100 < self.free_attack_percent()


async def get_combat_profile(session: AsyncSession, user_id: int) -> CombatProfile:
    row = await char_repo.get_combat_row(session, user_id)
    return CombatProfile(ranks=row.ranks, mastery=row.mastery, build=await get_build(session, user_id))
