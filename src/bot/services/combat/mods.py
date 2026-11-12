"""Боевые модификаторы — примитивы, из которых собираются способности путей, уникальных
техник, родословных, гениальностей и боссов (`docs/design/development_systems.md`,
«Архитектура реализации»).

Каждый уровень любой системы развития — это набор значений этих полей (или включение
нового поля). Поля складываются между системами (`+`) и масштабируются множителем
пробуждения (`scale`). Нулевой `CombatMods()` — бой ровно как без систем развития.

Единицы: доли (0.2 = 20%), кроме отмеченных. «Атака» — урон, который сторона наносит за
раунд; «ХП» — сколько урона выдерживает единица (по умолчанию = её мощь).
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, replace


# Поля, где из нескольких источников берётся самое раннее срабатывание (порог, период).
_MIN_FIELDS = frozenset({"reflect_every", "adapt_threshold", "reflect_burst_at"})
_UNSCALED_FIELDS = _MIN_FIELDS | frozenset({"rush_rounds"})


@dataclass(frozen=True, slots=True)
class CombatMods:
    # --- статичные ---
    attack: float = 0.0  # +к атаке
    durability: float = 0.0  # +к ХП единиц (Чёрные кости, Киокушинкай)
    reduction: float = 0.0  # доля входящего урона гасится (сверх поглощения Выносливости)
    pierce: float = 0.0  # доля брони противника (ХП-бонус, гашение, поглощение) игнорируется
    dodge: float = 0.0  # +к шансу уклонения (абсолютные доли)
    block: float = 0.0
    counter: float = 0.0
    flee: float = 0.0
    loss_save: float = 0.0  # +доля погибших, выживших после боя
    sure_hit: float = 0.0  # доля атаки, проходящая сквозь уклонение и блок противника
    crit_chance: float = 0.0
    crit_power: float = 0.0  # +к силе крита (база — `CRIT_BASE_BONUS`)
    bleed: float = 0.0  # доля дошедшего урона, бьющая противника ещё раз в начале следующего раунда
    cleave: float = 0.0  # удар по нескольким целям: +к атаке за «лишние» цели
    first_strike: float = 0.0  # доля армии противника, выбитая ДО боя
    suppress: float = 0.0  # реакции противника (уклонение/блок/контра/побег) слабее на эту долю
    heal: float = 0.0  # доля погибших за раунд возвращается в строй (медицина)
    # --- динамика по ходу боя ---
    overcome: float = 0.0  # нарастание атаки от полученного урона, сильнее против толпы слабых
    despair: float = 0.0  # шкала отчаяния против более сильных единиц: атака и меньше потерь
    reflect: float = 0.0  # доля дошедшего урона копится и возвращается противнику
    reflect_every: int = 0  # раз в N раундов выброс накопленного (0 — каждый раунд)
    absorb_store: float = 0.0  # доля входящего урона гасится и копится…
    absorb_return: float = 0.0  # …и возвращается в атаку с этим множителем
    adapt_threshold: float = 0.0  # «терпеть»: после потери этой доли армии…
    adapt_bonus: float = 0.0  # …атака растёт на эту долю
    adapt_guard: float = 0.0  # пока порог не пройден — дополнительное гашение урона
    rush: float = 0.0  # временный рывок: +атака…
    rush_rounds: int = 0  # …в первые N раундов
    ramp: float = 0.0  # +атака за каждый следующий раунд (разгон)…
    ramp_cap: float = 0.0  # …не больше этого
    opening: float = 0.0  # +атака только в первом раунде (удар одного шага)
    chaos: float = 0.0  # шанс хаоса в раунд: сокрушительный удар ×2 и сбой реакций противника
    # --- способности боссов ---
    grow_on_kill: float = 0.0  # атака растёт от доли убитых единиц противника (Ким Гапрен)
    heal_vs_weak: float = 0.0  # лечится, когда бьют слабые (Джинен)
    no_dodge: bool = False  # противник не может уклоняться (Элита)
    # --- до боя и первый удар ---
    pre_strike_share: float = 0.0  # доля армии, которая бьёт до первого раунда (Муджин)…
    pre_strike_power: float = 0.0  # …этой долей своей мощи, без реакций противника
    first_hit_ward: float = 0.0  # доля первого удара по армии, которая не проходит (Ямадзаки)
    # --- несколько атак ---
    multi_hit: float = 0.0  # удар проходит ещё по целям: сила дополнительного удара, 1.0 — ещё одна цель целиком (Тхэквондо)
    spill: float = 0.0  # доля лишнего урона по убитым переходит на следующих бойцов (Тхэквондо)
    rapid_step: float = 0.0  # +атак одним бойцом с каждым раундом (Полуночный меч)…
    rapid_cap: float = 0.0  # …не больше стольких дополнительных атак
    # --- накопление по ходу боя ---
    phantom_chance: float = 0.0  # шанс невидимого удара в раунд (растёт с раундами)…
    phantom_power: float = 0.0  # …удар на эту долю своей мощи, без реакций…
    phantom_growth: float = 0.0  # …каждый следующий сильнее на эту долю (стаки)
    bleed_linger: float = 0.0  # доля кровотечения, которая остаётся ещё на раунд (Ниндзюцу)
    endure_attack: float = 0.0  # +атака за каждый прожитый раунд (Александровы)
    endure_guard: float = 0.0  # +гашение урона за каждый прожитый раунд
    endure_unique: float = 0.0  # +мощь уников в армии за каждый прожитый раунд
    counter_power: float = 0.0  # контратака сильнее на эту долю
    # --- от соперника ---
    vs_stronger: float = 0.0  # +атака против более сильной армии, за каждое её удвоение (Киокушинкай)
    dominate: float = 0.0  # атака и прочность против более слабой армии, полная при перевесе ×4 (путь Отчаяния)
    overcome_gap: float = 0.0  # доля разрыва с более сильной армией, закрываемая за раунд (путь Преодоления)…
    overcome_gap_cap: float = 0.0  # …не больше стольких прибавок к мощи
    influence_power: float = 0.0  # +атака и прочность за каждые 100 своего влияния (Преодоление)
    influence_gap: float = 0.0  # +атака и прочность за каждые 100 влияния сверх влияния противника
    win_loss_save: float = 0.0  # при победе ещё эта доля погибших выживает
    revive_strike: float = 0.0  # доля павших за раунд встаёт и сразу бьёт ещё раз своей мощью (Преодоление)
    # --- отражение и поглощение ---
    reflect_burst_at: float = 0.0  # шкала отражения: выброс, когда получено столько от своей мощи…
    reflect_burst_power: float = 0.0  # …и выброс сильнее на эту долю
    reflect_loss_burst: float = 0.0  # выбито 50% и 75% армии: ответ на эту долю стартовой мощи
    absorb_power: float = 0.0  # +атака от поглощённого (полная при поглощении своей мощи)
    # --- уклонение ---
    dodge_counter: float = 0.0  # эта доля уклонившихся бьёт в ответ своей мощью
    dodge_surge: float = 0.0  # +атака от числа уклонений за бой (полная, когда уклонилась вся армия)
    dodge_true: float = 0.0  # эта доля уклонения работает, даже когда от удара «не увернуться» или реакции подавлены
    dodge_cap: float = 0.0  # выше потолок шанса уклонения
    # --- CQC (Менеджер Ким, 2026-11-12): стаки за убитых, каждый следующий тяжелее ---
    cqc: float = 0.0  # сила стаков: +атака от доли убитых единиц противника…
    cqc_accel: float = 0.0  # …и ускорение: стаки растут квадратично (чем дальше, тем больше стак)
    cqc_boost: float = 0.0  # стаки сильнее на эту долю (Александровы, путь Гарантированного удара)
    cqc_start: float = 0.0  # стартовые стаки — как будто эта доля противника уже убита (шкала CQC)
    # --- Сейрим (Сонджи Юк, 2026-11-12): контроль и сбивание чужих стаков ---
    stack_break: float = 0.0  # за раунд сбивает эту долю чужих стаков (отчаяние, CQC, рост от убитых…)
    grab_chance: float = 0.0  # шанс захвата в раунд…
    grab_share: float = 0.0  # …эта доля армии противника пропускает удар…
    throw_power: float = 0.0  # …и получает бросок на эту долю своей мощи
    grab_break: float = 0.0  # захват сбивает ещё эту долю стаков (1.0 — полностью)
    stun_share: float = 0.0  # в первом раунде эта доля армии противника не бьёт
    slow: float = 0.0  # замедление: реакции, рывок и удар первым у противника слабее на эту долю
    seirim_boost: float = 0.0  # Сейрим сильнее на эту долю (Муджин)

    def __add__(self, other: "CombatMods") -> "CombatMods":
        values = {}
        for f in fields(self):
            a, b = getattr(self, f.name), getattr(other, f.name)
            if isinstance(a, bool):
                values[f.name] = a or b
            elif f.name in _MIN_FIELDS:
                # Самый частый выброс отражения и самый ранний порог «терпения» из источников
                # (путь Адаптации + родословная Александровых не складывают порог до 60%).
                values[f.name] = min(x for x in (a, b) if x) if (a or b) else 0
            elif isinstance(a, int) and not isinstance(a, bool) and f.name.endswith("rounds"):
                values[f.name] = max(a, b)
            else:
                values[f.name] = a + b
        return CombatMods(**values)

    def scale(self, k: float) -> "CombatMods":
        """Масштаб численных бафов (множитель пробуждения, сила копии). Счётчики раундов и
        флаги не масштабируются."""
        if k == 1:
            return self
        values = {}
        for f in fields(self):
            v = getattr(self, f.name)
            if isinstance(v, bool) or f.name in _UNSCALED_FIELDS:
                values[f.name] = v
            else:
                values[f.name] = v * k
        return CombatMods(**values)

    @classmethod
    def of(cls, values: dict[str, float]) -> "CombatMods":
        unknown = set(values) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f"unknown combat mods: {sorted(unknown)}")
        return cls(**values)


NO_MODS = CombatMods()


def sum_mods(items) -> CombatMods:
    total = NO_MODS
    for m in items:
        total = total + m
    return total


@dataclass(frozen=True, slots=True)
class BattleBuild:
    """Всё, что сторона приносит в бой из систем развития.

    `by_source` — те же бафы по источникам (`"path"`, `"technique"`, `"bloodline"`,
    `"genius"`) — нужны, чтобы родословная Джинена могла скопировать конкретный источник
    противника. `copy_sources`/`copy_strength` — что и с какой силой копирует эта сторона.
    `rotation` — Бесконечная техника: наборы, переключаемые по раундам поверх `total`.
    """

    total: CombatMods = NO_MODS
    by_source: tuple[tuple[str, CombatMods], ...] = ()
    copy_sources: tuple[str, ...] = ()
    copy_strength: float = 0.0
    rotation: tuple[CombatMods, ...] = field(default_factory=tuple)

    def with_total(self, total: CombatMods) -> "BattleBuild":
        return replace(self, total=total)


NO_BUILD = BattleBuild()
