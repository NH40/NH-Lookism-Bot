"""Общий боевой движок — сражение двух армий-стопок (сервис, без БД и без Telegram).

Подтверждено пользователем 2026-09-29 (AskUserQuestion): **раунды над стопками**. Армия —
список стопок `CombatStack(key, unit_power, quantity)`, где мощь единицы = и её атака, и
её "ХП" (raw-notes: «у статиста есть мощь — это его атака и ХП, он может выдержать более
слабые атаки несколько раз и нанести сильный удар»). Поштучные дуэли невозможны — у
игроков могут быть миллиарды статистов (см. `db/models/extra.py`), поэтому каждая
случайность считается ОДНИМ биномиальным броском на стопку (`Random.binomialvariate`,
Python 3.12+), статистически эквивалентно броску за каждого.

Раунд (обе стороны одновременно, по состоянию на начало раунда):
1. Сторона наносит урон = `BATTLE_DAMAGE_FRACTION × живая_мощь × (1±VARIANCE)`.
2. Урон делится между стопками противника пропорционально их мощи; внутри стопки —
   поровну на единицу. Реакции единиц (raw-notes) — последовательные биномиальные броски:
   **побег** (уходит с поля живой, сохраняется для других боёв), **уклонение** (урон 0),
   **блок** (гасит урон, равный своей мощи — «блокирует атаку равно своей мощи»),
   **контратака** (получает урон полностью, но бьёт в ответ своей мощью).
3. Погибших = (дошедший урон / ХП единицы), дробная часть — вероятностным округлением
   (иначе слабый урон по сильной стопке никогда бы никого не убивал).
4. Урон контратак прилетает атаковавшей стороне в конце раунда, без реакций.

**Системы развития (2026-10-02)** приходят в бой как `CombatChances.build` — набор
примитивов `CombatMods` (`services/combat/mods.py`): множитель атаки и его динамика
(Преодоление, Отчаяние, «терпеть и ударить», рывок, разгон, удар одного шага, хаос),
прочность и гашение урона с пробитием, гарантированный удар, крит, кровотечение, удар до
боя, отражение и поглощение с возвратом, лечение, копирование источников противника и
ротация копий. Без систем (`NO_BUILD`) бой идёт ровно как раньше — ни одного лишнего
броска случайности.

Бой идёт до `BATTLE_MAX_ROUNDS` или пока у одной стороны не кончится живая мощь.
Побеждает тот, у кого осталось больше живой мощи (сбежавшие не считаются — ушли с
поля); ничья и взаимное уничтожение — победа защищающегося (атакующий обязан выбить
защиту, а не просто выжить). После боя `loss_save` доля погибших выживает.
"""
from __future__ import annotations

import math
from collections.abc import Hashable, Sequence
from dataclasses import dataclass, field
from random import Random

from bot.config.game import (
    BATTLE_BASE_BLOCK,
    BATTLE_BASE_COUNTER,
    BATTLE_BASE_DODGE,
    BATTLE_BASE_FLEE,
    BATTLE_BASE_LOSS_SAVE,
    BATTLE_CHAOS_SUPPRESS,
    BATTLE_CRIT_BASE_BONUS,
    BATTLE_DAMAGE_FRACTION,
    BATTLE_DAMAGE_VARIANCE,
    BATTLE_DESPAIR_RATIO_FOR_FULL,
    BATTLE_FIRST_STRIKE_MAX,
    BATTLE_GROW_ON_KILL_CAP,
    BATTLE_HEAL_MAX,
    BATTLE_LOSS_SAVE_MAX,
    BATTLE_MAX_ROUNDS,
    BATTLE_OVERCOME_CROWD_CAP,
    BATTLE_OVERCOME_TAKEN_CAP,
    BATTLE_REACTION_MAX,
    BATTLE_REACTIONS_TOTAL_MAX,
    BATTLE_REDUCTION_MAX,
    BATTLE_SURE_HIT_MAX,
)
from bot.constant import position_skill as ps
from bot.services.combat.mods import NO_BUILD, BattleBuild, CombatMods, sum_mods


@dataclass(frozen=True, slots=True)
class CombatStack:
    key: Hashable  # непрозрачный для движка идентификатор стопки — вызывающий код сам знает, что это
    # Мощь единицы; может быть дробной — бонусы игрока (Сила +1%/ранг) применяются
    # множителем без округления, иначе у слабых юнитов (F- = 10) +1% терялся бы.
    unit_power: float
    quantity: int
    # Свои прибавки к реакциям у бойцов стопки (школа учителя: ловкость — уклонение,
    # техника — блок, скорость — побег и контратака). По умолчанию 0 — как у всех.
    dodge: float = 0.0
    block: float = 0.0
    counter: float = 0.0
    flee: float = 0.0


@dataclass(frozen=True, slots=True)
class CombatChances:
    """Шансы реакции единицы на удар (характеристики и мастерство игрока) + бафы систем
    развития (`build`). У ботов — `base_chances()` без бафов."""

    dodge: float
    block: float
    counter: float
    flee: float
    loss_save: float
    # Доля входящего урона, которую армия поглощает (Выносливость игрока, пользователь
    # 2026-09-30: «поглощает часть урона»). У ботов — 0.
    absorb: float = 0.0
    build: BattleBuild = field(default=NO_BUILD)
    # Навыки позиций (`services/position_skill`): дебафы противнику на весь бой, условные
    # навыки по ходу боя, доля бойцов, не вышедших на бой (подкуп/паника шпиона противника —
    # не гибнут), потолок потерь за бой (Несокрушимый, 0 — нет).
    enemy_mods: CombatMods = field(default_factory=CombatMods)
    triggers: tuple["TriggerSpec", ...] = ()
    withheld: float = 0.0
    loss_cap: float = 0.0
    # Никита (абсолют): каждый свой павший — +1 мощи в шкалу; проиграл — шкала бьёт по армии
    # противника в конце боя (пока не кончится мощь шкалы).
    despair_strike: bool = False


@dataclass(frozen=True, slots=True)
class TriggerSpec:
    """Условный навык: пока условие `when` (`constant/position_skill.WHEN_*`) действует,
    стороне — `mods`, противнику — `enemy_mods`. Срабатывание пишется в журнал боя."""

    name: str
    when: str
    mods: CombatMods = field(default_factory=CombatMods)
    enemy_mods: CombatMods = field(default_factory=CombatMods)
    no_enemy_reactions: bool = False  # в активный раунд противник без реакций
    revive: float = 0.0  # разово: доля павших возвращается в строй
    loss_save: float = 0.0  # WHEN_ON_LOSS: ещё доля павших выживает
    enemy_extra_dead: float = 0.0  # WHEN_DEF_WIN: нападающий теряет ещё долю выживших


@dataclass(frozen=True, slots=True)
class RoundLog:
    """Раунд для журнала боя: урон сторон, убитые за раунд, хаос, сработавшие навыки."""

    number: int
    attacker_damage: int
    defender_damage: int
    attacker_kills: int  # убито нападающим за раунд
    defender_kills: int
    attacker_chaos: bool = False
    defender_chaos: bool = False
    attacker_fired: tuple[str, ...] = ()
    defender_fired: tuple[str, ...] = ()


def base_chances() -> CombatChances:
    return CombatChances(
        dodge=BATTLE_BASE_DODGE,
        block=BATTLE_BASE_BLOCK,
        counter=BATTLE_BASE_COUNTER,
        flee=BATTLE_BASE_FLEE,
        loss_save=BATTLE_BASE_LOSS_SAVE,
    )


@dataclass(frozen=True, slots=True)
class SideOutcome:
    initial_quantity: int
    initial_power: int
    remaining_power: int  # живые, оставшиеся на поле к концу боя (без сбежавших)
    dead: dict[Hashable, int]  # БЕЗВОЗВРАТНЫЕ потери по стопкам (уже за вычетом loss_save)
    fled: int

    @property
    def total_dead(self) -> int:
        return sum(self.dead.values())


@dataclass(frozen=True, slots=True)
class BattleResult:
    attacker_won: bool
    rounds: int
    attacker: SideOutcome
    defender: SideOutcome
    log: tuple[RoundLog, ...] = ()
    attacker_first_strike: int = 0  # выбито до боя (внезапность, ловушки, шпион)
    defender_first_strike: int = 0
    attacker_after: tuple[str, ...] = ()  # навыки, сработавшие после боя
    defender_after: tuple[str, ...] = ()


class _Side:
    def __init__(self, stacks: Sequence[CombatStack], chances: CombatChances) -> None:
        live = [s for s in stacks if s.quantity > 0 and s.unit_power > 0]
        self.power = {s.key: s.unit_power for s in live}
        self.bonus = {s.key: (s.dodge, s.block, s.counter, s.flee) for s in live if s.dodge or s.block or s.counter or s.flee}
        # Не вышедшие на бой (подкуп/паника) — не бьются и не гибнут, после боя на месте.
        withheld = min(0.9, max(0.0, chances.withheld))
        self.alive = {s.key: s.quantity - int(s.quantity * withheld) for s in live}
        self.withheld = sum(int(s.quantity * withheld) for s in live)
        self.dead = {s.key: 0 for s in live}
        self.fled = 0
        self.initial_quantity = sum(self.alive.values())
        self.initial_power = self.total_power()
        self.initial_avg = self.initial_power / self.initial_quantity if self.initial_quantity else 0.0
        self.chances = chances
        self.mods: CombatMods = chances.build.total  # после копирования — см. `simulate_battle`
        self.base_mods: CombatMods = self.mods  # без условных навыков раунда
        self.fired_once: set[str] = set()  # постоянные/разовые условия, уже записанные в журнал
        self.prev_round_lost = 0.0  # доля армии, павшая в прошлом раунде (WHEN_HEAVY_ROUND)
        # Состояние динамических примитивов.
        self.taken = 0.0  # дошедший урон за бой (Преодоление)
        self.kills = 0  # убито единиц противника (Ким Гапрен)
        self.reflect_store = 0.0
        self.absorb_store = 0.0
        self.pending_bleed = 0.0  # урон кровотечения этой стороны по противнику в следующем раунде
        self.round_dead: dict[Hashable, int] = {}

    def total_power(self) -> int:
        return round(sum(q * self.power[k] for k, q in self.alive.items()))

    def alive_quantity(self) -> int:
        return sum(self.alive.values())

    def avg_unit_power(self) -> float:
        qty = self.alive_quantity()
        return self.total_power() / qty if qty else 0.0

    def lost_fraction(self) -> float:
        return sum(self.dead.values()) / self.initial_quantity if self.initial_quantity else 0.0


def _prob_round(x: float, rng: Random) -> int:
    whole = int(x)
    return whole + (1 if rng.random() < x - whole else 0)


def _conditional(p: float, already_used: float) -> float:
    """Последовательные биномиальные броски как мультиномиальное разбиение: шанс
    следующей реакции среди ещё не распределённых единиц."""
    remaining = 1.0 - already_used
    if remaining <= 0:
        return 0.0
    return min(1.0, p / remaining)


def _round_mods(side: _Side, round_number: int) -> CombatMods:
    rotation = side.chances.build.rotation
    if not rotation:
        return side.mods
    return side.mods + rotation[(round_number - 1) % len(rotation)]


def _despair_gauge(side: _Side, opponent: _Side, m: CombatMods) -> float:
    """Шкала отчаяния: насколько единица противника сильнее своей (логарифмически, полная
    при `BATTLE_DESPAIR_RATIO_FOR_FULL`) плюс собственные потери — «найти силы, когда всё
    плохо»."""
    if not m.despair or not side.initial_avg:
        return 0.0
    ratio = opponent.initial_avg / side.initial_avg
    gauge = math.log(ratio) / math.log(BATTLE_DESPAIR_RATIO_FOR_FULL) if ratio > 1 else 0.0
    return min(1.0, max(0.0, gauge) + side.lost_fraction() * 0.5)


def _attack_multiplier(side: _Side, opponent: _Side, m: CombatMods, round_number: int, rng: Random) -> float:
    mult = 1.0 + m.attack + m.cleave
    if m.overcome:
        taken = min(BATTLE_OVERCOME_TAKEN_CAP, side.taken / side.initial_power) if side.initial_power else 0.0
        crowd = (opponent.initial_quantity / side.initial_quantity) ** 0.5 if side.initial_quantity else 1.0
        mult += m.overcome * taken * min(BATTLE_OVERCOME_CROWD_CAP, max(1.0, crowd))
    if m.despair:
        mult += m.despair * _despair_gauge(side, opponent, m)
    if m.adapt_bonus and side.lost_fraction() >= m.adapt_threshold:
        mult += m.adapt_bonus
    if m.rush and round_number <= m.rush_rounds:
        mult += m.rush
    if m.ramp:
        mult += min(m.ramp_cap, m.ramp * (round_number - 1)) if m.ramp_cap else m.ramp * (round_number - 1)
    if m.opening and round_number == 1:
        mult += m.opening
    if m.grow_on_kill and side.initial_quantity:
        # Рост от числа убитых относительно своей численности: толпа слабых кормит босса,
        # немногие сильные — нет (raw-notes: «против него должны быть эффективны сильные»).
        mult += min(BATTLE_GROW_ON_KILL_CAP, m.grow_on_kill * side.kills / side.initial_quantity)
    if m.crit_chance:
        mult *= 1 + min(1.0, m.crit_chance) * (BATTLE_CRIT_BASE_BONUS + m.crit_power) * rng.uniform(0.5, 1.5)
    return max(0.0, mult)


def _reactions(defender: _Side, attacker_mods: CombatMods, chaos: bool) -> CombatChances:
    """Реакции защищающейся стороны в этом раунде: шансы игрока + бафы систем, минус
    подавление атакующего (и хаос), под общими потолками."""
    c, m = defender.chances, defender.mods
    dodge, block, counter, flee = c.dodge + m.dodge, c.block + m.block, c.counter + m.counter, c.flee + m.flee
    suppress = min(1.0, attacker_mods.suppress + (BATTLE_CHAOS_SUPPRESS if chaos else 0.0))
    if suppress:
        dodge, block, counter, flee = (x * (1 - suppress) for x in (dodge, block, counter, flee))
    if attacker_mods.no_dodge:
        dodge = 0.0
    values = [min(BATTLE_REACTION_MAX, max(0.0, x)) for x in (dodge, block, counter, flee)]
    total = sum(values)
    if total > BATTLE_REACTIONS_TOTAL_MAX:
        values = [x * BATTLE_REACTIONS_TOTAL_MAX / total for x in values]
    dodge, block, counter, flee = values
    return CombatChances(dodge=dodge, block=block, counter=counter, flee=flee, loss_save=c.loss_save, absorb=c.absorb)


def _armor(defender: _Side, attacker_mods: CombatMods) -> tuple[float, float]:
    """(доля гашения урона, множитель ХП) защищающейся стороны с учётом пробития атакующего."""
    m = defender.mods
    reduction = defender.chances.absorb + m.reduction
    if m.adapt_guard and defender.lost_fraction() < m.adapt_threshold:
        reduction += m.adapt_guard
    pierce = min(1.0, attacker_mods.pierce)
    reduction = min(BATTLE_REDUCTION_MAX, reduction) * (1 - pierce)
    hp_mult = 1 + m.durability * (1 - pierce)
    return reduction, hp_mult


def _with_stack_bonus(chances: CombatChances, bonus: tuple[float, float, float, float] | None) -> CombatChances:
    """Реакции стопки: общие шансы стороны + прибавки школы, под теми же потолками."""
    if not bonus:
        return chances
    values = [
        min(BATTLE_REACTION_MAX, base + add)
        for base, add in zip((chances.dodge, chances.block, chances.counter, chances.flee), bonus)
    ]
    total = sum(values)
    if total > BATTLE_REACTIONS_TOTAL_MAX:
        values = [x * BATTLE_REACTIONS_TOTAL_MAX / total for x in values]
    dodge, block, counter, flee = values
    return CombatChances(dodge=dodge, block=block, counter=counter, flee=flee, loss_save=chances.loss_save, absorb=chances.absorb)


def _resolve_incoming(
    side: _Side, damage: float, chances: CombatChances, rng: Random, hp_mult: float = 1.0
) -> tuple[float, float, int]:
    """Урон с реакциями. → (урон контратак в ответ, дошедший урон, погибших)."""
    total = side.total_power()
    if total == 0 or damage <= 0:
        return 0.0, 0.0, 0
    counter_damage = reached = 0.0
    deaths_total = 0
    for key, quantity in list(side.alive.items()):
        if quantity == 0:
            continue
        unit_power = side.power[key]
        per_unit = damage * (quantity * unit_power) / total / quantity
        stack_chances = _with_stack_bonus(chances, side.bonus.get(key))

        fled = rng.binomialvariate(quantity, stack_chances.flee)
        rest = quantity - fled
        c = stack_chances
        dodged = rng.binomialvariate(rest, _conditional(c.dodge, c.flee))
        rest -= dodged
        blocked = rng.binomialvariate(rest, _conditional(c.block, c.flee + c.dodge))
        rest -= blocked
        countered = rng.binomialvariate(rest, _conditional(c.counter, c.flee + c.dodge + c.block))
        # `rest` — те, кто принял удар целиком (обычные + контратаковавшие).
        effective = rest * per_unit + blocked * max(0.0, per_unit - unit_power)
        deaths = min(rest + blocked, _prob_round(effective / (unit_power * hp_mult), rng))

        side.alive[key] = quantity - fled - deaths
        side.dead[key] += deaths
        side.round_dead[key] = side.round_dead.get(key, 0) + deaths
        side.fled += fled
        counter_damage += countered * unit_power
        reached += effective
        deaths_total += deaths
    return counter_damage, reached, deaths_total


def _apply_plain_damage(side: _Side, damage: float, rng: Random, hp_mult: float = 1.0) -> tuple[float, int]:
    """Урон без реакций (контратаки, гарантированный удар, отражение, кровотечение).
    → (дошедший урон, погибших)."""
    total = side.total_power()
    if total == 0 or damage <= 0:
        return 0.0, 0
    deaths_total = 0
    for key, quantity in list(side.alive.items()):
        if quantity == 0:
            continue
        unit_power = side.power[key]
        share = damage * (quantity * unit_power) / total
        deaths = min(quantity, _prob_round(share / (unit_power * hp_mult), rng))
        side.alive[key] = quantity - deaths
        side.dead[key] += deaths
        side.round_dead[key] = side.round_dead.get(key, 0) + deaths
        deaths_total += deaths
    return min(damage, float(total)), deaths_total


def _first_strike(target: _Side, fraction: float, rng: Random) -> int:
    """Удар до боя (Невидимые атаки): доля каждой стопки выбита до первого раунда."""
    fraction = min(BATTLE_FIRST_STRIKE_MAX, fraction)
    killed = 0
    for key, quantity in list(target.alive.items()):
        deaths = min(quantity, _prob_round(quantity * fraction, rng))
        target.alive[key] = quantity - deaths
        target.dead[key] += deaths
        killed += deaths
    return killed


def _heal(side: _Side, opponent: _Side, rng: Random) -> None:
    """Лечение в конце раунда: доля погибших за раунд встаёт в строй. Джинен-босс лечится
    тем сильнее, чем слабее единицы, которые его бьют."""
    m = side.mods
    fraction = m.heal
    if m.heal_vs_weak and side.avg_unit_power() > 0:
        weakness = max(0.0, min(1.0, 1 - opponent.avg_unit_power() / max(side.initial_avg, 1e-9)))
        fraction += m.heal_vs_weak * weakness
    fraction = min(BATTLE_HEAL_MAX, fraction)
    if fraction <= 0:
        return
    for key, count in side.round_dead.items():
        if count <= 0:
            continue
        revived = rng.binomialvariate(count, fraction)
        side.alive[key] += revived
        side.dead[key] -= revived


def _hit(attacker: _Side, defender: _Side, damage: float, am: CombatMods, chaos: bool, rng: Random) -> float:
    """Одна сторона бьёт другую за раунд. → урон контратак обратно атакующему."""
    dm = defender.mods
    if dm.absorb_store:
        stored = damage * min(0.9, dm.absorb_store)
        defender.absorb_store += stored
        damage -= stored
    reduction, hp_mult = _armor(defender, am)
    sure = damage * min(BATTLE_SURE_HIT_MAX, am.sure_hit) if am.sure_hit else 0.0
    counter, reached, deaths = _resolve_incoming(
        defender, (damage - sure) * (1 - reduction), _reactions(defender, am, chaos), rng, hp_mult
    )
    if sure:
        sure_reached, sure_deaths = _apply_plain_damage(defender, sure * (1 - reduction), rng, hp_mult)
        reached += sure_reached
        deaths += sure_deaths
    defender.taken += reached
    if dm.reflect:
        defender.reflect_store += reached * dm.reflect
    if am.bleed:
        attacker.pending_bleed += reached * am.bleed
    attacker.kills += deaths
    return counter


def _releases(side: _Side, opponent: _Side, m: CombatMods, round_number: int, rng: Random) -> None:
    """Выброс накопленного в конце раунда: отражение (раз в N раундов) и возврат
    поглощённого — урон без реакций по противнику."""
    _, hp_mult = _armor(opponent, m)
    if m.reflect and side.reflect_store and (not m.reflect_every or round_number % m.reflect_every == 0):
        _, kills = _apply_plain_damage(opponent, side.reflect_store, rng, hp_mult)
        side.kills += kills
        side.reflect_store = 0.0
    if m.absorb_return and side.absorb_store:
        _, kills = _apply_plain_damage(opponent, side.absorb_store * m.absorb_return, rng, hp_mult)
        side.kills += kills
        side.absorb_store = 0.0


def _outcome(side: _Side, loss_save: float, remaining_power: int, rng: Random) -> SideOutcome:
    dead = {}
    for key, count in side.dead.items():
        saved = rng.binomialvariate(count, loss_save) if count and loss_save > 0 else 0
        if count - saved:
            dead[key] = count - saved
    cap = side.chances.loss_cap
    total = sum(dead.values())
    if cap and side.initial_quantity and total > side.initial_quantity * cap:
        k = side.initial_quantity * cap / total  # Несокрушимый: сверх потолка — выжили
        dead = {key: int(count * k) for key, count in dead.items() if int(count * k)}
    return SideOutcome(
        initial_quantity=side.initial_quantity,
        initial_power=side.initial_power,
        remaining_power=remaining_power,
        dead=dead,
        fled=side.fled,
    )


def _copied(build: BattleBuild, opponent: BattleBuild) -> CombatMods:
    """Копирование (родословная Джинена): выбранные источники противника с силой копии."""
    if not build.copy_sources or not build.copy_strength:
        return CombatMods()
    picked = [mods for source, mods in opponent.by_source if source in build.copy_sources]
    return sum_mods(picked).scale(build.copy_strength)


def _loss_save(side: _Side, opponent: _Side) -> float:
    m = side.mods
    value = side.chances.loss_save + m.loss_save
    if m.despair:
        value += m.despair * _despair_gauge(side, opponent, m) * 0.5
    return min(BATTLE_LOSS_SAVE_MAX, value)


def _trigger_active(t: TriggerSpec, side: _Side, opponent: _Side, r: int) -> bool:
    w = t.when
    if w in (ps.WHEN_ROUND_1, ps.WHEN_DEF_ROUND_1):
        return r == 1
    if w == ps.WHEN_DEF_ROUNDS_1_2:
        return r <= 2
    if w == ps.WHEN_ROUNDS_2_3:
        return r in (2, 3)
    if w == ps.WHEN_ROUND_3:
        return r == 3
    if w == ps.WHEN_ROUND_4_PLUS:
        return r >= 4
    if w == ps.WHEN_EVERY_3RD:
        return r % 3 == 0
    if w == ps.WHEN_LOST_30:
        return side.lost_fraction() >= 0.3
    power = side.total_power() / side.initial_power if side.initial_power else 0.0
    if w == ps.WHEN_BELOW_50:
        return power < 0.5
    if w == ps.WHEN_BELOW_20:
        return power < 0.2
    if w == ps.WHEN_DEF_BELOW_30:
        return power < 0.3
    if w == ps.WHEN_HEAVY_ROUND:
        return side.prev_round_lost > 0.25
    if w == ps.WHEN_ENEMY_STRONGER:
        return r == 1 and opponent.initial_power > side.initial_power
    if w == ps.WHEN_WEAKER_ROUND_3:
        return r >= 3 and side.initial_power < opponent.initial_power
    return False  # WHEN_ON_LOSS / WHEN_DEF_WIN — после боя (`_after_battle`)


# Постоянные условия — в журнал один раз, при включении; раундовые — каждый активный раунд.
_LOG_ONCE = frozenset({
    ps.WHEN_LOST_30, ps.WHEN_BELOW_50, ps.WHEN_BELOW_20, ps.WHEN_DEF_BELOW_30, ps.WHEN_WEAKER_ROUND_3, ps.WHEN_ROUND_4_PLUS,
})


def _apply_triggers(side: _Side, opponent: _Side, r: int, rng: Random) -> tuple[CombatMods, CombatMods, list[str]]:
    """Условные навыки стороны в раунде → (бафы себе, дебафы противнику, имена для журнала)."""
    own, enemy, fired = CombatMods(), CombatMods(), []
    for t in side.chances.triggers:
        if not _trigger_active(t, side, opponent, r):
            continue
        own = own + t.mods + (CombatMods(suppress=1.0) if t.no_enemy_reactions else CombatMods())
        enemy = enemy + t.enemy_mods
        once = t.when in _LOG_ONCE or t.revive
        if once and t.name in side.fired_once:
            continue
        if t.revive:
            for key, count in list(side.dead.items()):
                back = _prob_round(count * min(0.5, t.revive), rng)
                if back:
                    side.alive[key] += back
                    side.dead[key] -= back
        if once:
            side.fired_once.add(t.name)
        fired.append(t.name)
    return own, enemy, fired


def _after_battle(side: _Side, opponent: _Side, won: bool, rng: Random) -> tuple[str, ...]:
    """Навыки после боя: «Отпор» (победа в защите — противник теряет ещё долю выживших),
    «Второй план» (поражение — ещё доля павших выживает; добавляется к спасению)."""
    fired = []
    for t in side.chances.triggers:
        if t.when == ps.WHEN_DEF_WIN and won and t.enemy_extra_dead:
            for key, count in list(opponent.alive.items()):
                extra = _prob_round(count * min(0.5, t.enemy_extra_dead), rng)
                if extra:
                    opponent.alive[key] -= extra
                    opponent.dead[key] += extra
            fired.append(t.name)
        elif t.when == ps.WHEN_ON_LOSS and not won and t.loss_save:
            fired.append(t.name)
    return tuple(fired)


DESPAIR_LOG = "Шкала отчаяния (Никита)"


def _despair(side: _Side, opponent: _Side, won: bool, rng: Random) -> tuple[str, ...]:
    """Проиграл с Никитой — шкала (1 павший = 1 мощь) бьёт по живым противника."""
    if won or not side.chances.despair_strike:
        return ()
    gauge = sum(side.dead.values())
    if gauge <= 0 or opponent.total_power() <= 0:
        return ()
    _, kills = _apply_plain_damage(opponent, float(gauge), rng)
    side.kills += kills
    return (f"{DESPAIR_LOG}: {gauge} мощи, убито {kills}",)


def _loss_save_after(side: _Side, opponent: _Side, won: bool) -> float:
    extra = sum(t.loss_save for t in side.chances.triggers if t.when == ps.WHEN_ON_LOSS) if not won else 0.0
    return min(BATTLE_LOSS_SAVE_MAX, _loss_save(side, opponent) + extra)


def simulate_battle(
    attacker: Sequence[CombatStack],
    defender: Sequence[CombatStack],
    *,
    attacker_chances: CombatChances,
    defender_chances: CombatChances,
    rng: Random | None = None,
) -> BattleResult:
    rng = rng or Random()
    a, d = _Side(attacker, attacker_chances), _Side(defender, defender_chances)
    a.mods = attacker_chances.build.total + _copied(attacker_chances.build, defender_chances.build) + defender_chances.enemy_mods
    d.mods = defender_chances.build.total + _copied(defender_chances.build, attacker_chances.build) + attacker_chances.enemy_mods
    a.base_mods, d.base_mods = a.mods, d.mods

    a_first = d_first = 0
    if a.mods.first_strike:
        a_first = _first_strike(d, a.mods.first_strike, rng)
        a.kills += a_first
    if d.mods.first_strike:
        d_first = _first_strike(a, d.mods.first_strike, rng)
        d.kills += d_first

    log: list[RoundLog] = []
    rounds = 0
    for round_number in range(1, BATTLE_MAX_ROUNDS + 1):
        a_power, d_power = a.total_power(), d.total_power()
        if a_power == 0 or d_power == 0:
            break
        rounds = round_number
        a_own, a_enemy, a_fired = _apply_triggers(a, d, round_number, rng)
        d_own, d_enemy, d_fired = _apply_triggers(d, a, round_number, rng)
        a.mods = a.base_mods + a_own + d_enemy
        d.mods = d.base_mods + d_own + a_enemy
        a_dead_before, d_dead_before = sum(a.dead.values()), sum(d.dead.values())
        am, dm = _round_mods(a, round_number), _round_mods(d, round_number)
        a.round_dead, d.round_dead = {}, {}

        # Кровотечение прошлого раунда — до обмена ударами.
        for side, opponent, m in ((a, d, am), (d, a, dm)):
            if side.pending_bleed:
                _, kills = _apply_plain_damage(opponent, side.pending_bleed, rng, _armor(opponent, m)[1])
                side.kills += kills
                side.pending_bleed = 0.0

        damage_to_d = a_power * BATTLE_DAMAGE_FRACTION * rng.uniform(1 - BATTLE_DAMAGE_VARIANCE, 1 + BATTLE_DAMAGE_VARIANCE)
        damage_to_a = d_power * BATTLE_DAMAGE_FRACTION * rng.uniform(1 - BATTLE_DAMAGE_VARIANCE, 1 + BATTLE_DAMAGE_VARIANCE)
        if am != _ZERO or dm != _ZERO:
            damage_to_d *= _attack_multiplier(a, d, am, round_number, rng)
            damage_to_a *= _attack_multiplier(d, a, dm, round_number, rng)
        a_chaos = bool(am.chaos) and rng.random() < am.chaos
        d_chaos = bool(dm.chaos) and rng.random() < dm.chaos
        if a_chaos:
            damage_to_d *= 2
        if d_chaos:
            damage_to_a *= 2

        counter_to_a = _hit(a, d, damage_to_d, am, a_chaos, rng)
        counter_to_d = _hit(d, a, damage_to_a, dm, d_chaos, rng)
        _apply_plain_damage(a, counter_to_a, rng, _armor(a, dm)[1])
        _apply_plain_damage(d, counter_to_d, rng, _armor(d, am)[1])

        _releases(a, d, am, round_number, rng)
        _releases(d, a, dm, round_number, rng)
        _heal(a, d, rng)
        _heal(d, a, rng)
        a_lost, d_lost = sum(a.dead.values()) - a_dead_before, sum(d.dead.values()) - d_dead_before
        a.prev_round_lost = a_lost / a.initial_quantity if a.initial_quantity else 0.0
        d.prev_round_lost = d_lost / d.initial_quantity if d.initial_quantity else 0.0
        log.append(RoundLog(
            number=round_number, attacker_damage=round(damage_to_d), defender_damage=round(damage_to_a),
            attacker_kills=max(0, d_lost), defender_kills=max(0, a_lost), attacker_chaos=a_chaos, defender_chaos=d_chaos,
            attacker_fired=tuple(a_fired), defender_fired=tuple(d_fired),
        ))

    a.mods, d.mods = a.base_mods, d.base_mods
    a_remaining, d_remaining = a.total_power(), d.total_power()
    attacker_won = a_remaining > 0 and (d_remaining == 0 or a_remaining > d_remaining)
    a_after, d_after = _after_battle(a, d, attacker_won, rng), _after_battle(d, a, not attacker_won, rng)
    a_after += _despair(a, d, attacker_won, rng)
    d_after += _despair(d, a, not attacker_won, rng)
    return BattleResult(
        attacker_won=attacker_won,
        rounds=rounds,
        attacker=_outcome(a, _loss_save_after(a, d, attacker_won), a.total_power(), rng),
        defender=_outcome(d, _loss_save_after(d, a, not attacker_won), d.total_power(), rng),
        log=tuple(log),
        attacker_first_strike=a_first,
        defender_first_strike=d_first,
        attacker_after=a_after,
        defender_after=d_after,
    )


_ZERO = CombatMods()
