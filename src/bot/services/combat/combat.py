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
from dataclasses import dataclass, field, replace
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
    BATTLE_INFLUENCE_STEP,
    BATTLE_PHANTOM_ROUND_CHANCE,
    BATTLE_POWER_DECISIVE_RATIO,
    battle_power_weight,
    BATTLE_PRE_STRIKE_MAX,
    BATTLE_REVIVE_STRIKE_MAX,
    BATTLE_VS_STRONGER_CAP,
    BATTLE_HEAL_MAX,
    BATTLE_LOSS_SAVE_MAX,
    BATTLE_LOSS_SAVE_SOURCE_MULT,
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
    # Разбор раунда для журнала (`services/combat/explain`): {"out": удар стороны, "in": что с ней сделал удар
    # противника, "healed": встали после лечения}. Только данные — текст строит explain.
    attacker_detail: dict = field(default_factory=dict)
    defender_detail: dict = field(default_factory=dict)


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
        self.hp_parts: dict[str, float] = {}  # из чего сложилась hp_bonus (журнал)
        self.det: dict = {}  # разбор текущего раунда (журнал)
        self.rx = [0, 0, 0, 0]  # за раунд: ушли, уклонились, заблокировали, контратаковали

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
    """Влияние в бою: своё и перевес над противником, за каждые `BATTLE_INFLUENCE_STEP` единиц, под потолком."""
    if not m.influence_gap and not m.influence_power:
        return 0.0
    own = side.chances.influence
    diff = max(0, own - opponent.chances.influence)
    return min(BATTLE_INFLUENCE_GAP_CAP, (m.influence_power * own + m.influence_gap * diff) / BATTLE_INFLUENCE_STEP)


def _refresh_dynamics(side: _Side, opponent: _Side, m: CombatMods, round_number: int) -> None:
    """Прочность и гашение, которые зависят от соперника и номера раунда."""
    side.hp_parts = {"gap": _gap_boost(side, opponent, m, round_number), "dominance": _dominance(side, opponent, m),
                     "influence": _influence_edge(side, opponent, m)}
    side.hp_bonus = sum(side.hp_parts.values())
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
    """Множитель атаки за раунд. Слагаемые пишутся в `side.det["out"]["parts"]` (журнал): (код, прибавка)."""
    parts: list[tuple[str, float]] = []
    stacks: list[tuple[str, float]] = []  # прибавки-стаки: их сбивает Сейрим противника (`side.broken`)
    for code, v in (("attack", m.attack), ("cleave", m.cleave)):
        if v:
            parts.append((code, v))
    for code, v in side.hp_parts.items():
        if v:
            parts.append((code, v))
    if m.endure_attack:
        stacks.append(("endure", m.endure_attack * (round_number - 1)))
    if m.vs_stronger and _power_ratio(side, opponent) > 1:
        parts.append(("vs_stronger", m.vs_stronger * min(BATTLE_VS_STRONGER_CAP, math.log2(_power_ratio(side, opponent)))))
    if m.absorb_power and side.initial_power:
        stacks.append(("absorb_power", m.absorb_power * min(BATTLE_ABSORB_POWER_CAP, side.absorbed / side.initial_power)))
    if m.dodge_surge and side.initial_quantity:
        stacks.append(("dodge_surge", m.dodge_surge * min(1.0, side.dodged / side.initial_quantity)))
    if m.overcome:
        taken = min(BATTLE_OVERCOME_TAKEN_CAP, side.taken / side.initial_power) if side.initial_power else 0.0
        crowd = (opponent.initial_quantity / side.initial_quantity) ** 0.5 if side.initial_quantity else 1.0
        stacks.append(("overcome", m.overcome * taken * min(BATTLE_OVERCOME_CROWD_CAP, max(1.0, crowd))))
    if m.despair:
        stacks.append(("despair", m.despair * _despair_gauge(side, opponent, m)))
    if m.adapt_bonus and side.lost_fraction() >= m.adapt_threshold:
        parts.append(("adapt", m.adapt_bonus))
    if m.rush and round_number <= m.rush_rounds:
        parts.append(("rush", m.rush * (1 - min(1.0, opponent.mods.slow))))  # замедление Сейрима
    if m.ramp:
        stacks.append(("ramp", min(m.ramp_cap, m.ramp * (round_number - 1)) if m.ramp_cap else m.ramp * (round_number - 1)))
    if m.opening and round_number == 1:
        parts.append(("opening", m.opening * (1 - min(1.0, opponent.mods.slow))))
    if m.grow_on_kill and side.initial_quantity:
        # Рост от числа убитых относительно своей численности: толпа слабых кормит босса,
        # немногие сильные — нет (raw-notes: «против него должны быть эффективны сильные»).
        stacks.append(("grow_on_kill", min(BATTLE_GROW_ON_KILL_CAP, m.grow_on_kill * side.kills / side.initial_quantity)))
    if m.cqc:
        stacks.append(("cqc", _cqc_bonus(side, opponent, m)))
    keep = 1 - min(1.0, side.broken)
    parts += [(code, v * keep) for code, v in stacks if v]
    if side.broken and any(v for _, v in stacks):
        parts.append(("broken", -sum(v for _, v in stacks) * (1 - keep)))
    mult = 1.0 + sum(v for _, v in parts)
    crit = 1.0
    if m.crit_chance:
        crit = 1 + min(1.0, m.crit_chance) * (BATTLE_CRIT_BASE_BONUS + m.crit_power) * rng.uniform(0.5, 1.5)
        mult *= crit
    out = side.det.setdefault("out", {})
    out["parts"] = [(c, round(v, 4)) for c, v in parts]
    out["crit"] = round(crit, 4)
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
        side.rx[0] += fled
        side.rx[1] += dodged
        side.rx[2] += blocked
        side.rx[3] += countered
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
        side.det["healed"] = side.det.get("healed", 0) + revived
        side.det["heal"] = round(fraction, 4)


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
    incoming = damage
    reduction, hp_mult = _armor(defender, am)
    sure = damage * min(BATTLE_SURE_HIT_MAX, am.sure_hit) if am.sure_hit else 0.0
    rx = _reactions(defender, am, chaos)
    counter, reached, deaths = _resolve_incoming(
        defender, (damage - sure) * (1 - reduction), rx, rng, hp_mult, min(1.0, am.spill)
    )
    dc = defender.chances
    defender.det["in"] = {
        "damage": round(incoming), "ward": EVENT_WARD in defender.events, "stored": round(defender.absorb_store) if dm.absorb_store else 0,
        "reduction": round(reduction, 4), "absorb": round(dc.absorb, 4), "armor": round(dm.reduction, 4),
        "guard": round(defender.guard_bonus, 4), "pierce": round(min(1.0, am.pierce), 4), "sure": round(sure),
        "chances": [round(rx.flee, 4), round(rx.dodge, 4), round(rx.block, 4), round(rx.counter, 4)],
        "suppress": round(min(1.0, am.suppress + am.slow + (BATTLE_CHAOS_SUPPRESS if chaos else 0.0)), 4),
        "hp": round(hp_mult, 4), "durability": round(dm.durability, 4),
    }
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
    defender.det["in"].update(reached=round(reached), deaths=deaths, counter=round(counter))
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
    return min(BATTLE_LOSS_SAVE_MAX, value * BATTLE_LOSS_SAVE_SOURCE_MULT)


def _despair_save_allowed(side: _Side, opponent: _Side, won: bool) -> bool:
    """Спасение павших от Отчаяния (пользователь 2026-11-27): только если бой проигран или на старте
    своя армия была слабее. Сильный, который победил, своих не спасает — иначе он и выигрывает,
    и почти ничего не теряет, а соперник падает в силе."""
    return not won or side.initial_power < opponent.initial_power


def _despair_loss_save(side: _Side, opponent: _Side, won: bool) -> float:
    """Вся часть спасения павших от Отчаяния: шкала пути, шкала отчаяния, бонус победы — под одним условием."""
    if not _despair_save_allowed(side, opponent, won):
        return 0.0
    m = side.mods
    value = m.despair_loss_save
    if m.despair:
        value += m.despair * _despair_gauge(side, opponent, m) * 0.5
    if won:
        value += m.win_loss_save
    return value


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
    extra += _despair_loss_save(side, opponent, won)
    return min(BATTLE_LOSS_SAVE_MAX, _loss_save(side, opponent) + extra * BATTLE_LOSS_SAVE_SOURCE_MULT)


def _stacks_power(stacks: Sequence[CombatStack]) -> float:
    return sum(s.unit_power * s.quantity for s in stacks if s.quantity > 0 and s.unit_power > 0)


def _attack_sources(side: _Side, own: CombatMods, enemy: CombatMods, extra: CombatMods | None) -> list[tuple[str, float]]:
    """Из чего сложилась прибавка «атака» стороны в раунде: источники билда, условные навыки, действие раунда,
    ослабление от противника; что не разложилось (зелья, пробуждение, мастерство) — «прочее»."""
    out: list[tuple[str, float]] = []
    for source, mods in side.chances.build.by_source:
        if mods.attack:
            out.append((source, mods.attack))
    if own.attack:
        out.append(("triggers", own.attack))
    if extra is not None and extra.attack:
        out.append(("action", extra.attack))
    if enemy.attack:
        out.append(("enemy", enemy.attack))
    rest = side.mods.attack - sum(v for _, v in out)
    if abs(rest) > 1e-4:  # зелья, пробуждение, мастерство, копирование, навыки позиций противника
        out.append(("other", rest))
    return [(k, round(v, 4)) for k, v in out]


def _toward(v: float, base: float, w: float) -> float:
    return base + (v - base) * w if v > base else v


def _weaken(ch: CombatChances, w: float) -> CombatChances:
    """Бонусы прокачки слабой стороны — на долю `w`: бафы систем (с ротацией и источниками для копирования),
    реакции и спасение сверх базы, поглощение, дебафы противнику, навыки позиций. Не трогает то, что наложил
    противник (`withheld` — подкуп/паника его шпиона)."""
    if w >= 1:
        return ch
    b = ch.build
    build = replace(b, total=b.total.scale(w), by_source=tuple((k, m.scale(w)) for k, m in b.by_source),
                    rotation=tuple(m.scale(w) for m in b.rotation))
    triggers = tuple(replace(t, mods=t.mods.scale(w), enemy_mods=t.enemy_mods.scale(w), revive=t.revive * w,
                             loss_save=t.loss_save * w, enemy_extra_dead=t.enemy_extra_dead * w) for t in ch.triggers)
    return replace(
        ch, build=build, dodge=_toward(ch.dodge, BATTLE_BASE_DODGE, w), block=_toward(ch.block, BATTLE_BASE_BLOCK, w),
        counter=_toward(ch.counter, BATTLE_BASE_COUNTER, w), flee=_toward(ch.flee, BATTLE_BASE_FLEE, w),
        loss_save=_toward(ch.loss_save, BATTLE_BASE_LOSS_SAVE, w), absorb=ch.absorb * w,
        enemy_mods=ch.enemy_mods.scale(w), triggers=triggers, loss_cap=ch.loss_cap * w,
    )


def _weaken_stacks(stacks: Sequence[CombatStack], w: float) -> Sequence[CombatStack]:
    """Свои реакции бойцов (школы учителей статистов) — тоже прокачка: на долю `w`."""
    if w >= 1:
        return stacks
    return [replace(s, dodge=s.dodge * w, block=s.block * w, counter=s.counter * w, flee=s.flee * w)
            if (s.dodge or s.block or s.counter or s.flee) else s for s in stacks]


class BattleRun:
    """Бой по раундам (2026-11-19, онлайн-бои): `play_round` — один раунд с действиями сторон (доп. модификаторы
    на раунд и множитель урона), `result` — итог. `simulate_battle` — тот же бой целиком без действий: порядок
    бросков случайности прежний, автобой даёт ровно те же результаты."""

    def __init__(
        self,
        attacker: Sequence[CombatStack],
        defender: Sequence[CombatStack],
        *,
        attacker_chances: CombatChances,
        defender_chances: CombatChances,
        rng: Random | None = None,
    ) -> None:
        rng = self.rng = rng or Random()
        # Влияние мощи: перевес R ослабляет прокачку слабой стороны, с ×DECISIVE бой решает мощь.
        pa, pd = _stacks_power(attacker), _stacks_power(defender)
        self.power_ratio = max(pa, pd) / min(pa, pd) if pa and pd else 1.0
        self.stronger = "a" if pa >= pd else "d"
        self.weights = {"a": 1.0, "d": 1.0}
        self.weights["d" if self.stronger == "a" else "a"] = battle_power_weight(self.power_ratio)
        attacker_chances = _weaken(attacker_chances, self.weights["a"])
        defender_chances = _weaken(defender_chances, self.weights["d"])
        attacker, defender = _weaken_stacks(attacker, self.weights["a"]), _weaken_stacks(defender, self.weights["d"])
        a, d = self.a, self.d = _Side(attacker, attacker_chances), _Side(defender, defender_chances)
        a.mods = attacker_chances.build.total + _copied(attacker_chances.build, defender_chances.build) + defender_chances.enemy_mods
        d.mods = defender_chances.build.total + _copied(defender_chances.build, attacker_chances.build) + attacker_chances.enemy_mods
        a.base_mods, d.base_mods = a.mods, d.mods
        self.a_first = self.d_first = 0
        if a.mods.first_strike:
            self.a_first = _first_strike(d, a.mods.first_strike * (1 - min(1.0, d.mods.slow)), rng)
            a.kills += self.a_first
        if d.mods.first_strike:
            self.d_first = _first_strike(a, d.mods.first_strike * (1 - min(1.0, a.mods.slow)), rng)
            d.kills += self.d_first
        self.a_pre = self.d_pre = 0
        if a.mods.pre_strike_share and a.mods.pre_strike_power:
            self.a_pre = _pre_strike(a, d, a.mods, rng)
        if d.mods.pre_strike_share and d.mods.pre_strike_power:
            self.d_pre = _pre_strike(d, a, d.mods, rng)
        self.log: list[RoundLog] = []
        self.rounds = 0
        self.ended = False

    @property
    def over(self) -> bool:
        return self.ended or self.rounds >= BATTLE_MAX_ROUNDS or self.a.total_power() == 0 or self.d.total_power() == 0

    def play_round(
        self, a_extra: CombatMods | None = None, d_extra: CombatMods | None = None, a_damage: float = 1.0, d_damage: float = 1.0,
    ) -> RoundLog | None:
        """Раунд. `*_extra` — модификаторы действия стороны на этот раунд, `*_damage` — множитель её урона."""
        a, d, rng = self.a, self.d, self.rng
        if self.over:
            self.ended = True
            return None
        round_number = self.rounds + 1
        a_power, d_power = a.total_power(), d.total_power()
        self.rounds = round_number
        a_own, a_enemy, a_fired = _apply_triggers(a, d, round_number, rng)
        d_own, d_enemy, d_fired = _apply_triggers(d, a, round_number, rng)
        a.mods = a.base_mods + a_own + d_enemy
        d.mods = d.base_mods + d_own + a_enemy
        if a_extra is not None:
            a.mods = a.mods + a_extra
        if d_extra is not None:
            d.mods = d.mods + d_extra
        a_dead_before, d_dead_before = sum(a.dead.values()), sum(d.dead.values())
        # Щит на следующий удар от действия раунда (Ямадзаки) — заново, даже если первый удар боя уже был.
        for side, extra in ((a, a_extra), (d, d_extra)):
            if extra is not None and extra.first_hit_ward > 0:
                side.warded = False
        # Удар до обмена от действия раунда (приём «Первым» и т.п., 2026-11-23); стартовый — в __init__.
        for side, target, extra in ((a, d, a_extra), (d, a, d_extra)):
            if extra is not None and extra.first_strike > 0:
                side.kills += _first_strike(target, extra.first_strike * (1 - min(1.0, target.mods.slow)), rng)
        am, dm = _round_mods(a, round_number), _round_mods(d, round_number)
        a.round_dead, d.round_dead = {}, {}
        a.events, d.events = [], []
        a.det, d.det = {}, {}
        a.rx, d.rx = [0, 0, 0, 0], [0, 0, 0, 0]
        _refresh_dynamics(a, d, am, round_number)
        _refresh_dynamics(d, a, dm, round_number)

        # Кровотечение прошлого раунда — до обмена ударами.
        for side, opponent, m in ((a, d, am), (d, a, dm)):
            if side.pending_bleed:
                _, kills = _apply_plain_damage(opponent, side.pending_bleed, rng, _armor(opponent, m)[1])
                side.kills += kills
                side.pending_bleed *= min(1.0, m.bleed_linger)

        a_var = rng.uniform(1 - BATTLE_DAMAGE_VARIANCE, 1 + BATTLE_DAMAGE_VARIANCE)
        damage_to_d = a_power * BATTLE_DAMAGE_FRACTION * a_var
        d_var = rng.uniform(1 - BATTLE_DAMAGE_VARIANCE, 1 + BATTLE_DAMAGE_VARIANCE)
        damage_to_a = d_power * BATTLE_DAMAGE_FRACTION * d_var
        for side, power, var, act, own, enemy, extra in ((a, a_power, a_var, a_damage, a_own, d_enemy, a_extra),
                                                         (d, d_power, d_var, d_damage, d_own, a_enemy, d_extra)):
            side.det["out"] = {"power": power, "var": round(var, 4), "act": round(act, 4),
                               "src": _attack_sources(side, own, enemy, extra)}
        damage_to_d *= a_damage
        damage_to_a *= d_damage
        if am != _ZERO or dm != _ZERO:
            damage_to_d *= _attack_multiplier(a, d, am, round_number, rng)
            damage_to_a *= _attack_multiplier(d, a, dm, round_number, rng)
        # Сейрим: сбить стаки противника, захват (часть его армии пропускает удар) и оглушение.
        a_hold, a_throw = _seirim(a, d, am, round_number, rng)
        d_hold, d_throw = _seirim(d, a, dm, round_number, rng)
        damage_to_a *= 1 - a_hold
        damage_to_d *= 1 - d_hold
        a.det["out"]["held"], d.det["out"]["held"] = round(d_hold, 4), round(a_hold, 4)
        a_chaos = bool(am.chaos) and rng.random() < am.chaos
        d_chaos = bool(dm.chaos) and rng.random() < dm.chaos
        if a_chaos:
            damage_to_d *= 2
        if d_chaos:
            damage_to_a *= 2
        a.det["out"].update(chaos=a_chaos, total=round(damage_to_d))
        d.det["out"].update(chaos=d_chaos, total=round(damage_to_a))

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
        for side in (a, d):
            side.det["rx"] = list(side.rx)
        a_lost, d_lost = sum(a.dead.values()) - a_dead_before, sum(d.dead.values()) - d_dead_before
        a.prev_round_lost = a_lost / a.initial_quantity if a.initial_quantity else 0.0
        d.prev_round_lost = d_lost / d.initial_quantity if d.initial_quantity else 0.0
        entry = RoundLog(
            number=round_number, attacker_damage=round(damage_to_d), defender_damage=round(damage_to_a),
            attacker_kills=max(0, d_lost), defender_kills=max(0, a_lost), attacker_chaos=a_chaos, defender_chaos=d_chaos,
            attacker_fired=tuple(a_fired + a.events), defender_fired=tuple(d_fired + d.events),
            attacker_detail=a.det, defender_detail=d.det,
        )
        self.log.append(entry)
        return entry

    def result(self) -> BattleResult:
        a, d, rng = self.a, self.d, self.rng
        a.mods, d.mods = a.base_mods, d.base_mods
        a_remaining, d_remaining = a.total_power(), d.total_power()
        attacker_won = a_remaining > 0 and (d_remaining == 0 or a_remaining > d_remaining)
        if self.power_ratio >= BATTLE_POWER_DECISIVE_RATIO:  # перевес ×10+ — побеждает сильный, что бы ни применял слабый
            attacker_won = self.stronger == "a"
        a_after, d_after = _after_battle(a, d, attacker_won, rng), _after_battle(d, a, not attacker_won, rng)
        a_after += _despair(a, d, attacker_won, rng)
        d_after += _despair(d, a, not attacker_won, rng)
        return BattleResult(
            attacker_won=attacker_won,
            rounds=self.rounds,
            attacker=_outcome(a, _loss_save_after(a, d, attacker_won), a.total_power(), rng),
            defender=_outcome(d, _loss_save_after(d, a, not attacker_won), d.total_power(), rng),
            log=tuple(self.log),
            attacker_first_strike=self.a_first,
            defender_first_strike=self.d_first,
            attacker_pre_strike=self.a_pre,
            defender_pre_strike=self.d_pre,
            attacker_after=a_after,
            defender_after=d_after,
        )


def simulate_battle(
    attacker: Sequence[CombatStack],
    defender: Sequence[CombatStack],
    *,
    attacker_chances: CombatChances,
    defender_chances: CombatChances,
    rng: Random | None = None,
) -> BattleResult:
    run = BattleRun(attacker, defender, attacker_chances=attacker_chances, defender_chances=defender_chances, rng=rng)
    while run.play_round() is not None:
        pass
    return run.result()


_ZERO = CombatMods()
