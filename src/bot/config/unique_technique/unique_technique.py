"""Уникальные техники — 11 техник по 10 уровней, учителя и их квесты (конфиг). Формат
уровней — `config/development`.

Пользователь 2026-10-02: на карте периодически появляются учителя, у каждого свой квест;
прошёл — получил его технику; дальше фрагменты УТ с босса Джинена качают её уровни. Владеть
можно несколькими, в бою активна одна (свап). Направления техник — от пользователя
(`docs/design/development_systems.md`), раскладка по уровням и числа — автор кода.
"""
from __future__ import annotations

from bot.constant.dev_quest import (
    TASK_BOSS_WIN,
    TASK_PERSONAL_TRAIN,
    TASK_RECRUIT,
    TASK_ROLL,
    TASK_TRAIN_EXTRAS,
    TASK_WIN_PVE,
    TASK_WIN_PVP,
)
from bot.constant.unique_technique import (
    TECH_BEAST,
    TECH_BLADE_HANDS,
    TECH_INVISIBLE,
    TECH_KYOKUSHIN,
    TECH_MA_TAESU,
    TECH_MIDNIGHT,
    TECH_MUAY_THAI,
    TECH_NINJUTSU,
    TECH_ONE_STEP,
    TECH_OVERCOME,
    TECH_TAEKWONDO,
)


def _c(**kw) -> dict:
    return {"combat": kw}


def _e(**kw) -> dict:
    return {"eco": kw}


def _s(combat: dict | None = None, eco: dict | None = None, **special) -> dict:
    return {"combat": combat or {}, "eco": eco or {}, "special": special}


LEVELS: dict[str, tuple[dict, ...]] = {
    # Звериный инстинкт (Том Ли): рывки, хаос, дикость. Меньше блоков, больше атак, пробитие брони.
    TECH_BEAST: (
        _c(attack=0.05, block=-0.02),
        _c(rush=0.10, rush_rounds=2),
        _c(chaos=0.05, pierce=0.05),
        _c(attack=0.05, block=-0.02),
        _c(rush=0.10, rush_rounds=3, suppress=0.05),
        _c(chaos=0.05, pierce=0.05),
        _c(attack=0.08, block=-0.02),
        _c(chaos=0.07, pierce=0.05),
        _c(rush=0.10, rush_rounds=4),
        _c(attack=0.12, chaos=0.05, pierce=0.12),
    ),
    # Невидимые атаки (Элита): скорость, уклонение, криты и удары из ниоткуда. В случайный момент враг
    # получает удар, каждый следующий такой удар сильнее: чем длиннее бой, тем их больше.
    TECH_INVISIBLE: (
        _c(dodge=0.04, phantom_chance=0.15, phantom_power=0.08),
        _c(crit_chance=0.05, dodge=0.02),
        _c(phantom_chance=0.10, phantom_growth=0.25),
        _c(dodge=0.04, flee=0.02),
        _c(crit_power=0.30, phantom_power=0.06),
        _c(phantom_chance=0.10, dodge=0.03),
        _c(crit_chance=0.07, phantom_growth=0.25),
        _c(phantom_power=0.06, crit_power=0.20),
        _c(phantom_chance=0.10, dodge=0.04),
        _c(phantom_chance=0.15, phantom_power=0.10, phantom_growth=0.50, crit_power=0.30),
    ),
    # Ниндзюцу (Курода Рюхей): бафы к разведке, наблюдению, безопасности и шпионажу, а в бою шанс и сила
    # крита, уклонение и долгое кровотечение.
    TECH_NINJUTSU: (
        _c(crit_chance=0.05, bleed=0.05),
        _e(scout=1),
        _c(crit_power=0.20, dodge=0.03),
        _s({"bleed": 0.05}, {"security": 1}),
        _c(crit_chance=0.05, bleed_linger=0.25),
        _e(logs=1, spy_chance=0.05),
        _c(crit_power=0.30, dodge=0.03),
        _s({"bleed": 0.10}, {"scout": 2, "sabotage_chance": 0.05}),
        _s({"crit_chance": 0.08, "bleed_linger": 0.25}, {"security": 1}),
        _s({"crit_power": 0.50, "bleed": 0.15, "dodge": 0.04}, {"scout": 3, "logs": 2, "spy_chance": 0.10, "spy_resist": 0.10}),
    ),
    # Преодоление (Джинран): влияние. Статисты сильнее от влияния, часть урона гасится, часть павших
    # выживает, а некоторые встают прямо в бою и бьют ещё раз. Камень резонанса.
    TECH_OVERCOME: (
        _c(influence_power=0.03, reduction=0.02),
        _s({"overcome": 0.15}, {"recruit_influence_cut": 0.10}),
        _c(revive_strike=0.02, durability=0.05),
        _s({"loss_save": 0.04}, {"influence_bonus": 0.05}),
        _c(influence_power=0.03, reduction=0.03),
        _c(revive_strike=0.02, overcome=0.15),
        _s({"despair": 0.10}, {"recruit_influence_cut": 0.10}),
        _c(influence_power=0.04, loss_save=0.05),
        _c(revive_strike=0.02, reduction=0.04),
        _s({"influence_power": 0.05, "overcome": 0.25, "revive_strike": 0.04, "despair": 0.15}, {"influence_bonus": 0.10}),
    ),
    # Киокушинкай: болезненные удары. Чем сильнее противник, тем сильнее бьёшь; пробивает чужую прочность,
    # держит свою, блоки и контратаки лучше.
    TECH_KYOKUSHIN: (
        _c(durability=0.06, vs_stronger=0.05),
        _c(pierce=0.08, attack=0.03),
        _c(attack=0.05, block=0.03),
        _c(vs_stronger=0.08, pierce=0.07),
        _c(durability=0.08, counter=0.03),
        _c(attack=0.06, pierce=0.10),
        _c(vs_stronger=0.10, block=0.03),
        _c(durability=0.10, counter=0.03),
        _c(pierce=0.10, attack=0.05),
        _c(attack=0.07, vs_stronger=0.15, pierce=0.15, durability=0.08),
    ),
    # Тхэквондо (Хансу): контратаки и уклонение, главное — удар по нескольким целям: один удар проходит
    # сразу по нескольким бойцам, остаток урона от убитого переходит на следующего, реакции врага слабеют.
    TECH_TAEKWONDO: (
        _c(multi_hit=0.08, dodge=0.02),
        _c(counter=0.03, spill=0.25),
        _c(multi_hit=0.08),
        _c(dodge=0.02, suppress=0.05),
        _c(multi_hit=0.10, counter=0.03),
        _c(spill=0.25),
        _c(multi_hit=0.10, suppress=0.05),
        _c(counter=0.04, dodge=0.03),
        _c(multi_hit=0.12),
        _c(multi_hit=0.12, spill=0.50, suppress=0.08, counter=0.03),
    ),
    # Кулак Ма Тэсу: сокрушительный удар, «одной рукой сносить камни».
    TECH_MA_TAESU: (
        _c(attack=0.08),
        _c(crit_power=0.25),
        _c(attack=0.08),
        _c(pierce=0.05),
        _c(crit_chance=0.08),
        _c(attack=0.10),
        _c(opening=0.30),
        _c(crit_power=0.35),
        _c(attack=0.12),
        _c(attack=0.22, crit_power=0.50, pierce=0.05),
    ),
    # Удар одного шага (Гансоп): шаг и удар огромной силы — мастерство Скорости и Силы усиливают первый
    # удар (`opening_per_mastery` × ступени мастерства, см. Build).
    TECH_ONE_STEP: (
        _c(opening=0.20),
        _s(opening_per_mastery=0.05),
        _c(opening=0.20),
        _c(dodge=0.03, attack=0.03),
        _s(opening_per_mastery=0.05),
        _c(sure_hit=0.05, attack=0.04),
        _c(opening=0.30),
        _s(opening_per_mastery=0.05),
        _c(first_strike=0.02),
        _s({"opening": 0.50, "attack": 0.05}, opening_per_mastery=0.10),
    ),
    # Руки-лезвия (Джин Чан): режущие удары — пробитие и кровотечение.
    TECH_BLADE_HANDS: (
        _c(bleed=0.07, attack=0.03),
        _c(pierce=0.07),
        _c(bleed=0.07),
        _c(crit_chance=0.07),
        _c(pierce=0.10, attack=0.04),
        _c(bleed=0.07, crit_power=0.20),
        _c(bleed=0.10, bleed_linger=0.15),
        _c(sure_hit=0.07),
        _c(pierce=0.12, attack=0.05),
        _c(bleed=0.20, pierce=0.12, bleed_linger=0.20, attack=0.05),
    ),
    # Муай-тай (Брэгдак): временно становиться сильнее.
    TECH_MUAY_THAI: (
        _c(rush=0.10, rush_rounds=2),
        _c(durability=0.06),
        _c(rush=0.10),
        _c(counter=0.04, attack=0.03),
        _c(rush=0.10, rush_rounds=3),
        _c(attack=0.05),
        _c(rush=0.10),
        _c(reduction=0.05),
        _c(rush=0.10, rush_rounds=4),
        _c(rush=0.20, attack=0.07, durability=0.06),
    ),
    # Полуночный меч: разгон. С каждым раундом боец успевает больше атак и бьёт сильнее, на максимуме
    # 8 атак за ход. Раскрывается в длинном бою.
    TECH_MIDNIGHT: (
        _c(rapid_step=0.25, rapid_cap=1.0),
        _c(ramp=0.05, ramp_cap=0.20),
        _c(rapid_step=0.15, rapid_cap=1.0),
        _c(dodge=0.04),
        _c(rapid_step=0.15, rapid_cap=1.0),
        _c(crit_chance=0.05, durability=0.08),
        _c(rapid_step=0.15, rapid_cap=1.0),
        _c(ramp=0.05, ramp_cap=0.25, durability=0.08),
        _c(rapid_step=0.15, rapid_cap=1.0),
        _c(rapid_step=0.15, rapid_cap=2.0, ramp=0.08, ramp_cap=0.40, reduction=0.05),
    ),
}

# Квест учителя — задания в игре (пользователь: «у каждого учителя свой квест»).
TEACHER_QUESTS: dict[str, dict[str, int]] = {
    TECH_BEAST: {TASK_WIN_PVE: 5, TASK_BOSS_WIN: 1, TASK_TRAIN_EXTRAS: 3},
    TECH_INVISIBLE: {TASK_WIN_PVP: 2, TASK_WIN_PVE: 3, TASK_ROLL: 3},
    TECH_NINJUTSU: {TASK_WIN_PVP: 3, TASK_PERSONAL_TRAIN: 3, TASK_BOSS_WIN: 1},
    TECH_OVERCOME: {TASK_WIN_PVE: 8, TASK_BOSS_WIN: 2, TASK_PERSONAL_TRAIN: 3},
    TECH_KYOKUSHIN: {TASK_TRAIN_EXTRAS: 5, TASK_WIN_PVE: 4, TASK_PERSONAL_TRAIN: 2},
    TECH_TAEKWONDO: {TASK_TRAIN_EXTRAS: 4, TASK_WIN_PVP: 2, TASK_RECRUIT: 10},
    TECH_MA_TAESU: {TASK_WIN_PVE: 6, TASK_PERSONAL_TRAIN: 4, TASK_BOSS_WIN: 1},
    TECH_ONE_STEP: {TASK_PERSONAL_TRAIN: 6, TASK_WIN_PVE: 3, TASK_TRAIN_EXTRAS: 3},
    TECH_BLADE_HANDS: {TASK_WIN_PVP: 3, TASK_BOSS_WIN: 2, TASK_WIN_PVE: 3},
    TECH_MUAY_THAI: {TASK_WIN_PVE: 5, TASK_WIN_PVP: 2, TASK_TRAIN_EXTRAS: 3},
    TECH_MIDNIGHT: {TASK_BOSS_WIN: 2, TASK_WIN_PVP: 2, TASK_ROLL: 5},
}

TECHNIQUE_LEVEL_COST_PER_LEVEL = 20  # 2-й — 40, 10-й — 200; до 10-го — 1 080 фрагментов УТ


def technique_level_cost(next_level: int, discount: float = 0.0) -> int:
    return max(1, int(TECHNIQUE_LEVEL_COST_PER_LEVEL * next_level * (1 - min(0.6, discount))))


def eased_quest(tasks: dict[str, int], *, speed: float = 0.0, skip: int = 0) -> dict[str, int]:
    """Задания учителя с бафами обучения (Хансу, Джинен с путём Бесконечной техники): `speed` — каждое
    задание меньше на эту долю, `skip` — столько самых больших заданий засчитываются сразу. Хотя бы
    одно задание остаётся всегда."""
    eased = {task: max(1, round(n * (1 - min(0.6, speed)))) for task, n in tasks.items()}
    for task, _ in sorted(eased.items(), key=lambda kv: -kv[1])[: max(0, min(skip, len(eased) - 1))]:
        del eased[task]
    return eased


TECHNIQUE_SWAP_COOLDOWN_SECONDS = 15 * 60

# Тренировка техники (пользователь 2026-10-12): каждый уровень 2–10 — цепочка «Тренировки →
# тренировка техники → учитель этой техники → оплата → его квест → уровень за фрагменты».
# Числа — автора кода: оплата растёт с уровнем (2-й — 15 000, 10-й — 135 000, всего 675 000 🪙),
# квест — исходный квест учителя, на каждый уровень выше 2-го +25% к каждому заданию.
TECH_TRAINING_PRICE_PER_LEVEL = 150_000  # пользователь 2026-10-14
TECH_TRAINING_QUEST_STEP = 0.25


def tech_training_price(next_level: int) -> int:
    return TECH_TRAINING_PRICE_PER_LEVEL * (next_level - 1)


def tech_training_quest(code: str, next_level: int) -> dict[str, int]:
    scale = 1 + TECH_TRAINING_QUEST_STEP * max(0, next_level - 2)
    return {task: max(1, round(n * scale)) for task, n in TEACHER_QUESTS[code].items()}
