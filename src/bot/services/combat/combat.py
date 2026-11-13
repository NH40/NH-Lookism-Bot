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
    BATTLE_ABSORB_POWER_CAP,
    BATTLE_BREAK_DECAY,
    BATTLE_CQC_CAP,
    BATTLE_CQC_CROWD_CAP,
    BATTLE_COPY_MAX,
    BATTLE_GRAB_SHARE_MAX,
    BATTLE_STUN_MAX,
    BATTLE_FIRST_STRIKE_MAX,
    BATTLE_GROW_ON_KILL_CAP,
    BATTLE_INFLUENCE_GAP_CAP,
    BATTLE_PHANTOM_ROUND_CHANCE,
    BATTLE_PRE_STRIKE_MAX,
    BATTLE_REVIVE_STRIKE_MAX,
    BATTLE_VS_STRONGER_CAP,
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
    unique: bool = False  # уникальный персонаж (`endure_unique`)


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
    # Влияние стороны: `influence_gap` считает разницу с влиянием противника.
    influence: int = 0


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
    # Для шкал путей (`services/path_gauge`).
    taken: float = 0.0  # дошедший урон за бой
    absorbed: float = 0.0  # поглощённый урон
    dodged: int = 0  # сколько раз бойцы уклонились
    kills: int = 0  # убито бойцов противника

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
    attacker_pre_strike: int = 0  # выбито ударом до боя (Муджин)
    defender_pre_strike: int = 0
    attacker_after: tuple[str, ...] = ()  # навыки, сработавшие после боя
    defender_after: tuple[str, ...] = ()


class _Side:
    def __init__(self, stacks: Sequence[CombatStack], chances: CombatChances) -> None:
        live = [s for s in stacks if s.quantity > 0 and s.unit_power > 0]
        self.power = {s.key: s.unit_power for s in live}
        self.bonus = {s.key: (s.dodge, s.block, s.counter, s.flee) for s in live if s.dodge or s.block or s.counter or s.flee}
        self.unique_keys = [s.key for s in live if s.unique]
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
        self.absorbed = 0.0  # поглощено за бой
        self.dodged = 0  # уклонений за бой
        self.warded = False  # первый удар по армии уже был
        self.phantom_stacks = 0  # сколько невидимых ударов уже прошло
        self.reflect_gauge = 0.0  # получено с прошлого выброса отражения
        self.loss_bursts = 0  # сработавшие ответы на потери (50%, 75%)
        self.hp_bonus = 0.0  # прочность от динамики боя (разрыв, перевес, влияние)
        self.guard_bonus = 0.0  # гашение от динамики боя
        self.events: list[str] = []  # что сработало в этом раунде (журнал)
        self.broken = 0.0  # доля стаков, сбитая Сейримом противника (затухает по раундам)

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


def _power_ratio(side: _Side, opponent: _Side) -> float:
    """Во сколько раз стартовая мощь противника больше своей."""
    return opponent.initial_power / side.initial_power if side.initial_power else 1.0


def _gap_boost(side: _Side, opponent: _Side, m: CombatMods, round_number: int) -> float:
    """Путь Преодоления: с каждым раундом закрывает разрыв с более сильной армией."""
    if not m.overcome_gap:
        return 0.0
    gap = max(0.0, _power_ratio(side, opponent) - 1)
    return min(m.overcome_gap_cap, gap * min(1.0, m.overcome_gap * round_number))


def _dominance(side: _Side, opponent: _Side, m: CombatMods) -> float:
    """Путь Отчаяния: бонус против более слабой армии, полный при перевесе ×4."""
    if not m.dominate or not opponent.initial_power:
        return 0.0
    ratio = side.initial_power / opponent.initial_power
    return m.dominate * min(1.0, max(0.0, math.log2(ratio) / 2)) if ratio > 1 else 0.0


def _influence_edge(side: _Side, opponent: _Side, m: CombatMods) -> float:
    """Влияние в бою: своё и перевес над противником, за каждые 100 единиц, под потолком."""
    if not m.influence_gap and not m.influence_power:
        return 0.0
    own = side.chances.influence
    diff = max(0, own - opponent.chances.influence)
    return min(BATTLE_INFLUENCE_GAP_CAP, (m.influence_power * own + m.influence_gap * diff) / 100)


def _refresh_dynamics(side: _Side, opponent: _Side, m: CombatMods, round_number: int) -> None:
    """Прочность и гашение, которые зависят от соперника и номера раунда."""
    side.hp_bonus = _gap_boost(side, opponent, m, round_number) + _dominance(side, opponent, m) + _influence_edge(side, opponent, m)
    side.guard_bonus = m.endure_guard * (round_number - 1)
    if m.endure_unique and round_number > 1:
        for key in side.unique_keys:
            side.power[key] *= 1 + m.endure_unique


def _cqc_bonus(side: _Side, opponent: _Side, m: CombatMods) -> float:
    """Стаки CQC: доля убитых противника (+стартовые), рост с ускорением, сильнее против толпы."""
    if not m.cqc or not opponent.initial_quantity:
        return 0.0
    f = side.kills / opponent.initial_quantity + m.cqc_start
    crowd = (opponent.initial_quantity / side.initial_quantity) ** 0.5 if side.initial_quantity else 1.0
    crowd = min(BATTLE_CQC_CROWD_CAP, max(1.0, crowd))
    return min(BATTLE_CQC_CAP, m.cqc * (1 + m.cqc_boost) * (f + m.cqc_accel * f * f)) * crowd


def _seirim(side: _Side, opponent: _Side, m: CombatMods, round_number: int, rng: Random) -> tuple[float, float]:
    """Сейрим стороны `side` против `opponent`: сбивает стаки, захват, оглушение в 1-м раунде.
    → (доля армии противника, не бьющая в этом раунде; урон броском по противнику)."""
    if not (m.stack_break or m.grab_chance or m.stun_share):
        return 0.0, 0.0
    boost = 1 + m.seirim_boost
    hold = throw = 0.0
    if m.stack_break:
        kept = opponent.broken * BATTLE_BREAK_DECAY
        opponent.broken = min(1.0, kept + min(1.0, m.stack_break * boost) * (1 - kept))
    if m.stun_share and round_number == 1:
        hold = min(BATTLE_STUN_MAX, m.stun_share * boost)
        side.events.append(EVENT_STUN.format(p=round(hold * 100)))
    if m.grab_chance and rng.random() < min(1.0, m.grab_chance * boost):
        share = min(BATTLE_GRAB_SHARE_MAX, m.grab_share * boost)
        hold = min(0.9, hold + share)
        throw = opponent.total_power() * share * m.throw_power * boost
        if m.grab_break:
            opponent.broken = min(1.0, opponent.broken + min(1.0, m.grab_break * boost) * (1 - opponent.broken))
        side.events.append(EVENT_GRAB.format(p=round(share * 100)))
    return hold, throw


def _attack_multiplier(side: _Side, opponent: _Side, m: CombatMods, round_number: int, rng: Random) -> float:
    mult = 1.0 + m.attack + m.cleave + side.hp_bonus
    stacked = 0.0  # прибавки-стаки: их сбивает Сейрим противника (`side.broken`)
    if m.endure_attack:
        stacked += m.endure_attack * (round_number - 1)
    if m.vs_stronger and _power_ratio(side, opponent) > 1:
        mult += m.vs_stronger * min(BATTLE_VS_STRONGER_CAP, math.log2(_power_ratio(side, opponent)))
    if m.absorb_power and side.initial_power:
        stacked += m.absorb_power * min(BATTLE_ABSORB_POWER_CAP, side.absorbed / side.initial_power)
    if m.dodge_surge and side.initial_quantity:
        stacked += m.dodge_surge * min(1.0, side.dodged / side.initial_quantity)
    if m.overcome:
        taken = min(BATTLE_OVERCOME_TAKEN_CAP, side.taken / side.initial_power) if side.initial_power else 0.0
        crowd = (opponent.initial_quantity / side.initial_quantity) ** 0.5 if side.initial_quantity else 1.0
        stacked += m.overcome * taken * min(BATTLE_OVERCOME_CROWD_CAP, max(1.0, crowd))
    if m.despair:
        stacked += m.despair * _despair_gauge(side, opponent, m)
    if m.adapt_bonus and side.lost_fraction() >= m.adapt_threshold:
        mult += m.adapt_bonus
    if m.rush and round_number <= m.rush_rounds:
        mult += m.rush * (1 - min(1.0, opponent.mods.slow))  # замедление Сейрима
    if m.ramp:
        stacked += min(m.ramp_cap, m.ramp * (round_number - 1)) if m.ramp_cap else m.ramp * (round_number - 1)
    if m.opening and round_number == 1:
        mult += m.opening * (1 - min(1.0, opponent.mods.slow))
    if m.grow_on_kill and side.initial_quantity:
        # Рост от числа убитых относительно своей численности: толпа слабых кормит босса,
        # немногие сильные — нет (raw-notes: «против него должны быть эффективны сильные»).
        stacked += min(BATTLE_GROW_ON_KILL_CAP, m.grow_on_kill * side.kills / side.initial_quantity)
    if m.cqc:
        stacked += _cqc_bonus(side, opponent, m)
    mult += stacked * (1 - min(1.0, side.broken))
    if m.crit_chance:
        mult *= 1 + min(1.0, m.crit_chance) * (BATTLE_CRIT_BASE_BONUS + m.crit_power) * rng.uniform(0.5, 1.5)
    return max(0.0, mult)


def _reactions(defender: _Side, attacker_mods: CombatMods, chaos: bool) -> CombatChances:
    """Реакции защищающейся стороны в этом раунде: шансы игрока + бафы систем, минус
    подавление атакующего (и хаос), под общими потолками."""
    c, m = defender.chances, defender.mods
    dodge, block, counter, flee = c.dodge + m.dodge, c.block + m.block, c.counter + m.counter, c.flee + m.flee
    suppress = min(1.0, attacker_mods.suppress + attacker_mods.slow + (BATTLE_CHAOS_SUPPRESS if chaos else 0.0))
    raw_dodge = dodge
    if suppress:
        dodge, block, counter, flee = (x * (1 - suppress) for x in (dodge, block, counter, flee))
    if attacker_mods.no_dodge:
        dodge = 0.0
    if m.dodge_true:  # путь Уклонения: часть уклонения не сбить ничем
        dodge = max(dodge, raw_dodge * min(1.0, m.dodge_true))
    caps = (BATTLE_REACTION_MAX + m.dodge_cap, BATTLE_REACTION_MAX, BATTLE_REACTION_MAX, BATTLE_REACTION_MAX)
    values = [min(cap, max(0.0, x)) for cap, x in zip(caps, (dodge, block, counter, flee))]
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
    reduction += defender.guard_bonus
    pierce = min(1.0, attacker_mods.pierce)
    reduction = min(BATTLE_REDUCTION_MAX, reduction) * (1 - pierce)
    hp_mult = 1 + (m.durability + defender.hp_bonus) * (1 - pierce)
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
    side: _Side, damage: float, chances: CombatChances, rng: Random, hp_mult: float = 1.0, spill: float = 0.0
) -> tuple[float, float, int]:
    """Урон с реакциями. → (урон контратак в ответ, дошедший урон, погибших)."""
    total = side.total_power()
    if total == 0 or damage <= 0:
        return 0.0, 0.0, 0
    counter_damage = reached = overkill = 0.0
    deaths_total = 0
    m = side.mods
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
        side.dodged += dodged
        counter_damage += countered * unit_power * (1 + m.counter_power) + dodged * unit_power * m.dodge_counter
        reached += effective
        deaths_total += deaths
        if spill:
            overkill += max(0.0, effective - deaths * unit_power * hp_mult)
    if overkill:
        spilled, spill_deaths = _apply_plain_damage(side, overkill * spill, rng, hp_mult)
        reached += spilled
        deaths_total += spill_deaths
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
        # Лечение и «Преодоление» считают от одних павших: поднять больше, чем лежит, нельзя.
        revived = min(rng.binomialvariate(count, fraction), max(side.dead[key], 0))
        side.alive[key] += revived
        side.dead[key] -= revived


def _hit(attacker: _Side, defender: _Side, damage: float, am: CombatMods, chaos: bool, rng: Random) -> float:
    """Одна сторона бьёт другую за раунд. → урон контратак обратно атакующему."""
    dm = defender.mods
    if dm.first_hit_ward and not defender.warded:
        defender.warded = True
        damage *= 1 - min(1.0, dm.first_hit_ward)
        defender.events.append(EVENT_WARD)
    if dm.absorb_store:
        stored = damage * min(0.9, dm.absorb_store)
        defender.absorb_store += stored
        defender.absorbed += stored
        damage -= stored
    reduction, hp_mult = _armor(defender, am)
    sure = damage * min(BATTLE_SURE_HIT_MAX, am.sure_hit) if am.sure_hit else 0.0
    counter, reached, deaths = _resolve_incoming(
        defender, (damage - sure) * (1 - reduction), _reactions(defender, am, chaos), rng, hp_mult, min(1.0, am.spill)
    )
    if sure:
        sure_reached, sure_deaths = _apply_plain_damage(defender, sure * (1 - reduction), rng, hp_mult)
        reached += sure_reached
        deaths += sure_deaths
    defender.taken += reached
    if dm.reflect:
        defender.reflect_store += reached * dm.reflect
        defender.reflect_gauge += reached
    if am.bleed:
        attacker.pending_bleed += reached * am.bleed
    attacker.kills += deaths
    return counter


def _releases(side: _Side, opponent: _Side, m: CombatMods, round_number: int, rng: Random) -> None:
    """Выброс накопленного в конце раунда: отражение (раз в N раундов) и возврат
    поглощённого — урон без реакций по противнику."""
    _, hp_mult = _armor(opponent, m)
    gauge_full = bool(m.reflect_burst_at) and side.initial_power and side.reflect_gauge >= m.reflect_burst_at * side.initial_power
    if m.reflect and side.reflect_store and (gauge_full or not m.reflect_every or round_number % m.reflect_every == 0):
        burst = 1 + m.reflect_burst_power if gauge_full else 1.0
        _, kills = _apply_plain_damage(opponent, side.reflect_store * burst, rng, hp_mult)
        side.kills += kills
        side.reflect_store = 0.0
        if gauge_full:
            side.reflect_gauge = 0.0
            side.events.append(EVENT_REFLECT_BURST)
    if m.reflect_loss_burst:
        lost = side.lost_fraction()
        for step, threshold in enumerate((0.5, 0.75), 1):
            if side.loss_bursts < step and lost >= threshold:
                side.loss_bursts = step
                _, kills = _apply_plain_damage(opponent, side.initial_power * m.reflect_loss_burst, rng, hp_mult)
                side.kills += kills
                side.events.append(EVENT_REFLECT_LOSS)
    if m.absorb_return and side.absorb_store:
        _, kills = _apply_plain_damage(opponent, side.absorb_store * m.absorb_return, rng, hp_mult)
        side.kills += kills
        side.absorb_store = 0.0


def _pre_strike(side: _Side, target: _Side, m: CombatMods, rng: Random) -> int:
    """Удар до боя (Муджин): доля армии бьёт долей своей мощи, без реакций противника."""
    damage = side.total_power() * min(1.0, m.pre_strike_share) * m.pre_strike_power
    damage = min(damage, target.total_power() * BATTLE_PRE_STRIKE_MAX)
    reduction, hp_mult = _armor(target, m)
    _, kills = _apply_plain_damage(target, damage * (1 - reduction), rng, hp_mult)
    side.kills += kills
    return kills


def _extra_attacks(attacker: _Side, defender: _Side, damage: float, m: CombatMods, chaos: bool, round_number: int, rng: Random) -> float:
    """Дополнительные атаки раунда. Полуночный меч: с каждым раундом бойцы успевают больше атак;
    Тхэквондо: удар проходит ещё по целям. → урон контратак обратно."""
    counter = 0.0
    if m.rapid_step:
        # разгон — тоже стаки: Сейрим противника сбивает его (`attacker.broken`)
        extra = min(m.rapid_cap, m.rapid_step * (round_number - 1)) * (1 - min(1.0, attacker.broken))
        whole = int(extra) + (1 if rng.random() < extra - int(extra) else 0)
        for _ in range(whole):
            counter += _hit(attacker, defender, damage, m, chaos, rng)
        if whole:
            attacker.events.append(EVENT_RAPID.format(n=whole + 1))
    if m.multi_hit:
        rest, targets = m.multi_hit, 1
        while rest > 0:
            counter += _hit(attacker, defender, damage * min(1.0, rest), m, chaos, rng)
            rest -= 1.0
            targets += 1
        attacker.events.append(EVENT_MULTI.format(n=targets))
    return counter


def _phantom(side: _Side, opponent: _Side, m: CombatMods, round_number: int, rng: Random) -> None:
    """Невидимые атаки: в случайный момент бьёт долей своей мощи, без реакций; чем больше ударов
    уже прошло, тем сильнее следующий, и чем длиннее бой, тем выше шанс."""
    if not m.phantom_chance or not m.phantom_power:
        return
    chance = m.phantom_chance + BATTLE_PHANTOM_ROUND_CHANCE * (round_number - 1)
    if rng.random() >= chance:
        return
    damage = side.total_power() * m.phantom_power * (1 + m.phantom_growth * side.phantom_stacks * (1 - min(1.0, side.broken)))
    side.phantom_stacks += 1
    _, kills = _apply_plain_damage(opponent, damage, rng, _armor(opponent, m)[1])
    side.kills += kills
    side.events.append(EVENT_PHANTOM.format(n=side.phantom_stacks, kills=kills))


def _revive_strike(side: _Side, opponent: _Side, m: CombatMods, rng: Random) -> None:
    """Техника Преодоления: часть павших за раунд встаёт и сразу бьёт ещё раз."""
    share = min(BATTLE_REVIVE_STRIKE_MAX, m.revive_strike)
    if share <= 0:
        return
    damage = revived_total = 0
    for key, count in side.round_dead.items():
        if count <= 0:
            continue
        revived = min(rng.binomialvariate(count, share), max(side.dead[key], 0))
        if revived:
            side.alive[key] += revived
            side.dead[key] -= revived
            damage += revived * side.power[key]
            revived_total += revived
    if revived_total:
        _, kills = _apply_plain_damage(opponent, damage, rng, _armor(opponent, m)[1])
        side.kills += kills
        side.events.append(EVENT_REVIVE.format(n=revived_total))


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
        taken=side.taken,
        absorbed=side.absorbed,
        dodged=side.dodged,
        kills=side.kills,
    )


def _copied(build: BattleBuild, opponent: BattleBuild) -> CombatMods:
    """Копирование (родословная Джинена): выбранные источники противника с силой копии."""
    if not build.copy_sources or not build.copy_strength:
        return CombatMods()
    picked = [mods for source, mods in opponent.by_source if source in build.copy_sources]
    return sum_mods(picked).scale(min(BATTLE_COPY_MAX, build.copy_strength))


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
# Журнал боя: что сработало за раунд.
EVENT_WARD = "первый удар не прошёл"
EVENT_REFLECT_BURST = "выброс шкалы отражения"
EVENT_REFLECT_LOSS = "ответ на потери"
EVENT_RAPID = "{n} атаки за ход"
EVENT_MULTI = "удар по {n} целям"
EVENT_PHANTOM = "невидимый удар №{n}: убито {kills}"
EVENT_REVIVE = "павшие встали и ударили: {n}"
EVENT_GRAB = "Сейрим: захват {p}% армии и бросок"
EVENT_STUN = "Сейрим: оглушение {p}% армии"


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
    if won:
        extra += side.mods.win_loss_save
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
        a_first = _first_strike(d, a.mods.first_strike * (1 - min(1.0, d.mods.slow)), rng)
        a.kills += a_first
    if d.mods.first_strike:
        d_first = _first_strike(a, d.mods.first_strike * (1 - min(1.0, a.mods.slow)), rng)
        d.kills += d_first
    a_pre = d_pre = 0
    if a.mods.pre_strike_share and a.mods.pre_strike_power:
        a_pre = _pre_strike(a, d, a.mods, rng)
    if d.mods.pre_strike_share and d.mods.pre_strike_power:
        d_pre = _pre_strike(d, a, d.mods, rng)

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
        a.events, d.events = [], []
        _refresh_dynamics(a, d, am, round_number)
        _refresh_dynamics(d, a, dm, round_number)

        # Кровотечение прошлого раунда — до обмена ударами.
        for side, opponent, m in ((a, d, am), (d, a, dm)):
            if side.pending_bleed:
                _, kills = _apply_plain_damage(opponent, side.pending_bleed, rng, _armor(opponent, m)[1])
                side.kills += kills
                side.pending_bleed *= min(1.0, m.bleed_linger)

        damage_to_d = a_power * BATTLE_DAMAGE_FRACTION * rng.uniform(1 - BATTLE_DAMAGE_VARIANCE, 1 + BATTLE_DAMAGE_VARIANCE)
        damage_to_a = d_power * BATTLE_DAMAGE_FRACTION * rng.uniform(1 - BATTLE_DAMAGE_VARIANCE, 1 + BATTLE_DAMAGE_VARIANCE)
        if am != _ZERO or dm != _ZERO:
            damage_to_d *= _attack_multiplier(a, d, am, round_number, rng)
            damage_to_a *= _attack_multiplier(d, a, dm, round_number, rng)
        # Сейрим: сбить стаки противника, захват (часть его армии пропускает удар) и оглушение.
        a_hold, a_throw = _seirim(a, d, am, round_number, rng)
        d_hold, d_throw = _seirim(d, a, dm, round_number, rng)
        damage_to_a *= 1 - a_hold
        damage_to_d *= 1 - d_hold
        a_chaos = bool(am.chaos) and rng.random() < am.chaos
        d_chaos = bool(dm.chaos) and rng.random() < dm.chaos
        if a_chaos:
            damage_to_d *= 2
        if d_chaos:
            damage_to_a *= 2

        counter_to_a = _hit(a, d, damage_to_d, am, a_chaos, rng)
        counter_to_d = _hit(d, a, damage_to_a, dm, d_chaos, rng)
        if am.rapid_step or am.multi_hit:
            counter_to_a += _extra_attacks(a, d, damage_to_d, am, a_chaos, round_number, rng)
        if dm.rapid_step or dm.multi_hit:
            counter_to_d += _extra_attacks(d, a, damage_to_a, dm, d_chaos, round_number, rng)
        _apply_plain_damage(a, counter_to_a, rng, _armor(a, dm)[1])
        _apply_plain_damage(d, counter_to_d, rng, _armor(d, am)[1])
        for side, opponent, throw, m in ((a, d, a_throw, am), (d, a, d_throw, dm)):
            if throw:
                _, kills = _apply_plain_damage(opponent, throw, rng, _armor(opponent, m)[1])
                side.kills += kills

        _releases(a, d, am, round_number, rng)
        _releases(d, a, dm, round_number, rng)
        _phantom(a, d, am, round_number, rng)
        _phantom(d, a, dm, round_number, rng)
        _revive_strike(a, d, am, rng)
        _revive_strike(d, a, dm, rng)
        _heal(a, d, rng)
        _heal(d, a, rng)
        a_lost, d_lost = sum(a.dead.values()) - a_dead_before, sum(d.dead.values()) - d_dead_before
        a.prev_round_lost = a_lost / a.initial_quantity if a.initial_quantity else 0.0
        d.prev_round_lost = d_lost / d.initial_quantity if d.initial_quantity else 0.0
        log.append(RoundLog(
            number=round_number, attacker_damage=round(damage_to_d), defender_damage=round(damage_to_a),
            attacker_kills=max(0, d_lost), defender_kills=max(0, a_lost), attacker_chaos=a_chaos, defender_chaos=d_chaos,
            attacker_fired=tuple(a_fired + a.events), defender_fired=tuple(d_fired + d.events),
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
        attacker_pre_strike=a_pre,
        defender_pre_strike=d_pre,
        attacker_after=a_after,
        defender_after=d_after,
    )


_ZERO = CombatMods()
