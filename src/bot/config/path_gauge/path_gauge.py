"""Шкалы путей (конфиг).

Пользователь 2026-11-04: «у каждого пути своя шкала, заполняя шкалу мы становимся сильнее». Шкала
живёт в `user_paths.gauge`, хранится между боями и сбрасывается вместе с путём. Потолок шкалы зависит
от уровня пути (`GAUGE_CAP_PER_LEVEL`): на 10-м уровне — `GAUGE_MAX`.

Эффект считается долей `значение / GAUGE_MAX`: `combat`/`eco` — бафы при полной шкале, `tiers` — ступени
(что открывается при заполнении до порога; у таких полей уровни, а не доли). Откуда шкала растёт — в
`services/path_gauge`. У Пути тренировок своя шкала — КПД (`config/unique_path`), у Отражения шкала живёт
только внутри боя (`CombatMods.reflect_burst_at`), поэтому здесь их нет.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from bot.constant.unique_path import (
    PATH_ABSORPTION,
    PATH_ADAPTATION,
    PATH_BUSINESS,
    PATH_COPY,
    PATH_DESPAIR,
    PATH_EVASION,
    PATH_FORESIGHT,
    PATH_INFINITE,
    PATH_OVERCOME,
    PATH_SENSORY,
    PATH_SURE_HIT,
)

GAUGE_MAX = 100.0
GAUGE_CAP_PER_LEVEL = 10.0

# Сколько шкалы даёт один бой при прочих равных. Бой с игроком — в `GAUGE_PVP_WEIGHT` раз больше боя с
# ботами и боссами (их легче набить), потолок за один бой — `GAUGE_MAX_PER_BATTLE`.
GAUGE_PVP_WEIGHT = 2.0
GAUGE_MAX_PER_BATTLE = 6.0
# Шкала Бизнесмена: столько NHCoin заработка = 1 единица шкалы.
GAUGE_BUSINESS_COINS = 100_000
# Шкала Сенсорики: за разведку и за саботаж.
GAUGE_SENSORY_SCOUT = 1.0
GAUGE_SENSORY_SABOTAGE = 2.0
# Шкала Предвидения: за разведку.
GAUGE_FORESIGHT_SCOUT = 0.5
# Шкала копирования: за подъём уровня любой техники.
GAUGE_COPY_TECH_LEVEL = 3.0


@dataclass(frozen=True, slots=True)
class GaugeSpec:
    combat: dict = field(default_factory=dict)  # боевые бафы при полной шкале
    eco: dict = field(default_factory=dict)  # небоевые бафы при полной шкале
    special: dict = field(default_factory=dict)  # особые числа при полной шкале
    tiers: tuple[tuple[float, dict], ...] = ()  # (порог шкалы, небоевые бафы-ступени)


PATH_GAUGES: dict[str, GaugeSpec] = {
    # За бои, больше — против более сильных. Бафает мощь и влияние, режет требования вербовки.
    PATH_OVERCOME: GaugeSpec(
        combat={"attack": 0.40, "durability": 0.25},
        eco={"influence_bonus": 0.25, "recruit_influence_cut": 0.10},
    ),
    # За победы и убитых: чем больше побеждал, тем сильнее и тем больше своих сохраняешь.
    PATH_DESPAIR: GaugeSpec(combat={"attack": 0.35, "loss_save": 0.10, "win_loss_save": 0.10}),
    # За поглощённый урон.
    PATH_ABSORPTION: GaugeSpec(combat={"durability": 0.20, "attack": 0.20, "absorb_store": 0.04}),
    # За бои с другими игроками. Сила копии растёт, Джинен ускоряет.
    PATH_COPY: GaugeSpec(combat={"attack": 0.15}, special={"memory_copy": 0.40}),
    # Та же шкала копирования: определяет, сколько техник активно (`config/unique_path`).
    PATH_INFINITE: GaugeSpec(special={"infinite_power": 0.05}),  # было 0.10 — симуляция 2026-11-14
    # За бои и разведку: реакции в бою и ступени разведки, шпионажа и безопасности.
    PATH_FORESIGHT: GaugeSpec(
        combat={"dodge": 0.08, "counter": 0.08, "loss_save": 0.05},
        tiers=((30.0, {"scout": 1, "spy_chance": 0.05}), (60.0, {"scout": 2, "logs": 1, "security": 1}), (90.0, {"scout": 3, "logs": 2, "security": 2, "foresight": 3})),
    ),
    # За разведку и саботаж: новые метки и сила саботажа.
    PATH_SENSORY: GaugeSpec(
        eco={"sabotage_chance": 0.15, "sabotage_loot": 0.30},
        tiers=((40.0, {"marks": 1, "security_pierce": 1}), (80.0, {"marks": 2, "security_pierce": 2})),
    ),
    # За победы: чем дольше воюешь, тем сильнее бьёшь.
    PATH_SURE_HIT: GaugeSpec(combat={"attack": 0.35, "pierce": 0.15, "sure_hit": 0.10}),
    # За полученный урон: «терпишь — становишься сильнее». Бафы и статистам, и уникам.
    PATH_ADAPTATION: GaugeSpec(combat={"attack": 0.30, "durability": 0.25, "reduction": 0.05, "endure_unique": 0.03}),
    # За уклонения.
    PATH_EVASION: GaugeSpec(combat={"dodge": 0.05, "attack": 0.15, "dodge_counter": 0.08, "dodge_cap": 0.03}),
    # За заработанные деньги: доход, пассивный доход, фрагменты.
    PATH_BUSINESS: GaugeSpec(eco={"income": 0.40, "passive_income": 3000, "fragment_bonus": 0.30}),
}


# Шкала усиливается вместе с путём (`config/unique_path.PATH_BALANCE`).
def _balanced(gauges: dict[str, GaugeSpec]) -> dict[str, GaugeSpec]:
    from dataclasses import replace

    from bot.config.unique_path.unique_path import PATH_BALANCE

    return {code: replace(g, combat={f: round(v * PATH_BALANCE.get(code, 1.0), 4) for f, v in g.combat.items()}) for code, g in gauges.items()}


PATH_GAUGES = _balanced(PATH_GAUGES)


def gauge_cap(level: int) -> float:
    return min(GAUGE_MAX, max(0, level) * GAUGE_CAP_PER_LEVEL)
