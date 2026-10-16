"""Подготовка схватки с навыками позиций и журнал боя (сервис).

`matchup()` — единая точка для всех боёв игрока: бросает шпиона нападающего, отключает
позиции цели, собирает шансы обеих сторон по роли и типу боя (`CombatProfile.chances`),
добавляет кражи шпиона («Украсть технику», «Кукловод»). `journal()` превращает итог боя
в строки журнала (бот — свёрнутая цитата под отчётом, Mini App — блок «Ход боя»).
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from random import Random

from bot.constant.absolute import ABS_ARIAN
from bot.constant.build import SOURCE_TECHNIQUE
from bot.constant.position_skill import KIND_ATK, KIND_AURA, ROLE_ATTACK, ROLE_DEFENSE
from bot.services.combat import BattleResult, CombatChances, base_chances
from bot.services.combat.mods import NO_MODS, CombatMods
from bot.services.position_skill.position_skill import NO_EFFECTS, NO_SPY, SpyOutcome, _split, resolve_spy
from bot.texts.card import POSITION_LABELS
from bot.texts.position_skill import (
    JOURNAL_AFTER,
    JOURNAL_CHAOS,
    JOURNAL_DISABLED,
    JOURNAL_FIRED,
    JOURNAL_FIRST_STRIKE_FOE,
    JOURNAL_FIRST_STRIKE_MINE,
    JOURNAL_PRE,
    JOURNAL_RESULT_LOSS,
    JOURNAL_RESULT_WIN,
    JOURNAL_ROUND,
    JOURNAL_SPY_BLOCKED,
    JOURNAL_SPY_FAIL,
    JOURNAL_SPY_OK,
    JOURNAL_WITHHELD,
    SIDE_FOE,
    SIDE_YOU,
)
from bot.utils.formatting import esc, format_number


@dataclass(frozen=True)
class Matchup:
    attacker: CombatChances
    defender: CombatChances
    spy: SpyOutcome = NO_SPY
    arian: bool = False  # абсолюты цели заблокированы Арианом нападающего


def matchup(attacker, defender=None, *, vs: tuple[str, ...], defender_chances: CombatChances | None = None,
            attacker_kw: dict | None = None, defender_role: str = ROLE_DEFENSE, scouted: bool = False,
            attacker_stacks=None, defender_stacks=None, rng: Random | None = None) -> Matchup:
    """`attacker`/`defender` — `CombatProfile` игроков (защитник `None` — боты/босс, тогда его
    шансы — `defender_chances`). `defender_role` — `ROLE_ATTACK`, если защитник принял вызов и
    бьётся лагерем атаки (навыки «в защите» тогда не работают)."""
    rng = rng or Random()
    target = (defender.build.positions or NO_EFFECTS) if defender is not None else NO_EFFECTS
    spy = resolve_spy(attacker.build.positions or NO_EFFECTS, target, rng)
    a = attacker.chances(role=ROLE_ATTACK, vs=vs, spy_cast=spy, **(attacker_kw or {}))
    arian = defender is not None and ABS_ARIAN in attacker.build.absolutes and bool(defender.build.absolutes)
    if defender is not None:
        d = defender.chances(role=defender_role, vs=vs, spy_taken=spy, no_absolutes=arian)
    else:
        base = defender_chances or base_chances()
        d = replace(base, withheld=spy.withheld, build=base.build.with_total(base.build.total + spy.enemy_mods))
    extra = NO_MODS
    if defender is not None and spy.special.get("steal_technique"):
        tech = dict(defender.build.battle.by_source).get(SOURCE_TECHNIQUE)
        if tech is not None:
            extra = extra + tech.scale(min(1.0, spy.special["steal_technique"]))
    if defender is not None and spy.special.get("steal_skill"):
        pool = [s for s in target.skills if s.skill.kind in (KIND_AURA, KIND_ATK)]
        if pool:
            extra = extra + _split(rng.choice(pool))[0]
    # Отчёт разведки на цель: «Знай врага» (+атака) и «Вскрыть слабости» (−блок цели).
    apos = attacker.build.positions or NO_EFFECTS
    if scouted and apos.get("scouted_attack"):
        extra = extra + CombatMods(attack=apos.get("scouted_attack"))
    if scouted and apos.get("scouted_enemy_block"):
        a = replace(a, enemy_mods=a.enemy_mods + CombatMods(block=apos.get("scouted_enemy_block")))
    extra = extra + _stack_bonus(apos, attacker_stacks)
    if extra != NO_MODS:
        a = replace(a, build=a.build.with_total(a.build.total + extra))
    if defender is not None and defender_stacks:
        d_extra = _stack_bonus(target, defender_stacks)
        if d_extra != NO_MODS:
            d = replace(d, build=d.build.with_total(d.build.total + d_extra))
    return Matchup(attacker=a, defender=d, spy=spy, arian=arian)


def _stack_bonus(positions, stacks) -> CombatMods:
    """«Первое поколение» (+мощь уников в армии), «Старая гвардия» (три старших ранга),
    «Молодая кровь» (младшие ранги): бонус ко всей армии пропорционально доле этой мощи."""
    if not stacks or positions is None:
        return NO_MODS
    card, top, low = positions.get("card_power"), positions.get("top_ranks_power"), positions.get("low_ranks_power")
    if not (card or top or low):
        return NO_MODS
    total = sum(s.unit_power * s.quantity for s in stacks) or 1.0
    extras = [s for s in stacks if not (isinstance(s.key, tuple) and s.key and s.key[0] in ("u", "c"))]
    share_card = sum(s.unit_power * s.quantity for s in stacks if isinstance(s.key, tuple) and s.key and s.key[0] == "u") / total
    powers = sorted({s.unit_power for s in extras}, reverse=True)
    share_top = share_low = 0.0
    if powers:
        threshold = powers[min(2, len(powers) - 1)]
        share_top = sum(s.unit_power * s.quantity for s in extras if s.unit_power >= threshold) / total
        median = powers[len(powers) // 2]
        share_low = sum(s.unit_power * s.quantity for s in extras if s.unit_power < median) / total
    x = card * share_card + top * share_top + low * share_low
    return CombatMods(attack=x, durability=x) if x else NO_MODS


def journal(result: BattleResult, spy: SpyOutcome = NO_SPY, *, viewer_is_attacker: bool = True) -> tuple[str, ...]:
    """Строки журнала с точки зрения смотрящего (нападающего или защитника), HTML бота."""
    lines: list[str] = []
    pre: list[str] = []
    for e in spy.events:
        template = JOURNAL_SPY_OK if e.success else JOURNAL_SPY_BLOCKED if e.blocked else JOURNAL_SPY_FAIL
        pre.append(template.format(name=esc(e.name), card=esc(e.card_name)))
    if spy.disable:
        pre.append(JOURNAL_DISABLED.format(positions=", ".join(POSITION_LABELS.get(p, p) for p in sorted(spy.disable))))
    if spy.withheld:
        withheld = round(result.defender.initial_quantity / max(1e-9, 1 - spy.withheld) * spy.withheld)
        pre.append(JOURNAL_WITHHELD.format(count=format_number(withheld)))
    me_first, foe_first = (
        (result.attacker_first_strike, result.defender_first_strike) if viewer_is_attacker
        else (result.defender_first_strike, result.attacker_first_strike)
    )
    if me_first:
        pre.append(JOURNAL_FIRST_STRIKE_MINE.format(count=format_number(me_first)))
    if foe_first:
        pre.append(JOURNAL_FIRST_STRIKE_FOE.format(count=format_number(foe_first)))
    if pre:
        lines.append(JOURNAL_PRE)
        lines.extend(pre if viewer_is_attacker else [p for p in pre if not p.startswith("🕵️")])
    for r in result.log:
        mine = viewer_is_attacker
        dealt, taken = (r.attacker_damage, r.defender_damage) if mine else (r.defender_damage, r.attacker_damage)
        kills, lost = (r.attacker_kills, r.defender_kills) if mine else (r.defender_kills, r.attacker_kills)
        my_chaos, foe_chaos = (r.attacker_chaos, r.defender_chaos) if mine else (r.defender_chaos, r.attacker_chaos)
        lines.append(JOURNAL_ROUND.format(
            n=r.number, you=SIDE_YOU, dealt=format_number(dealt), chaos=JOURNAL_CHAOS if my_chaos else "",
            foe=SIDE_FOE, taken=format_number(taken), foe_chaos=JOURNAL_CHAOS if foe_chaos else "",
            kills=format_number(kills), lost=format_number(lost),
        ))
        my_fired, foe_fired = (r.attacker_fired, r.defender_fired) if mine else (r.defender_fired, r.attacker_fired)
        if my_fired:
            lines.append(JOURNAL_FIRED.format(side=SIDE_YOU, names=", ".join(esc(n) for n in my_fired)))
        if foe_fired:
            lines.append(JOURNAL_FIRED.format(side=SIDE_FOE, names=", ".join(esc(n) for n in foe_fired)))
    my_after, foe_after = (result.attacker_after, result.defender_after) if viewer_is_attacker else (result.defender_after, result.attacker_after)
    if my_after:
        lines.append(JOURNAL_AFTER.format(side=SIDE_YOU, names=", ".join(esc(n) for n in my_after)))
    if foe_after:
        lines.append(JOURNAL_AFTER.format(side=SIDE_FOE, names=", ".join(esc(n) for n in foe_after)))
    won = result.attacker_won if viewer_is_attacker else not result.attacker_won
    lines.append((JOURNAL_RESULT_WIN if won else JOURNAL_RESULT_LOSS).format(rounds=result.rounds))
    return tuple(lines)


def journal_block(lines: tuple[str, ...]) -> str:
    """Журнал под отчётом бота — свёрнутая цитата (раскрывается тапом)."""
    from bot.texts.position_skill import JOURNAL_TITLE

    if not lines:
        return ""
    return f"\n\n<blockquote expandable>{JOURNAL_TITLE}\n" + "\n".join(lines) + "</blockquote>"


__all__ = ["Matchup", "matchup", "journal", "journal_block", "ROLE_ATTACK", "ROLE_DEFENSE"]
