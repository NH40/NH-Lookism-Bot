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


def _s(combat: dict | None = None, **special) -> dict:
    return {"combat": combat or {}, "special": special}


LEVELS: dict[str, tuple[dict, ...]] = {
    # Звериный инстинкт (Том Ли): жёсткость, дикость, большой урон, большая защита.
    TECH_BEAST: (
        _c(attack=0.04),
        _c(durability=0.06),
        _c(rush=0.15, rush_rounds=2),
        _c(reduction=0.04),
        _c(attack=0.05, durability=0.05),
        _c(counter=0.04),
        _c(suppress=0.08),
        _c(durability=0.10),
        _c(rush=0.15, rush_rounds=3),
        _c(attack=0.10, reduction=0.06),
    ),
    # Невидимые атаки (Элита): удары из слепых зон; вершина — бить до сражения.
    TECH_INVISIBLE: (
        _c(dodge=0.03),
        _c(suppress=0.05),
        _c(sure_hit=0.05),
        _c(crit_chance=0.05),
        _c(dodge=0.03, suppress=0.05),
        _c(first_strike=0.02),
        _c(sure_hit=0.10),
        _c(crit_power=0.25),
        _c(first_strike=0.03),
        _c(first_strike=0.05, suppress=0.10),
    ),
    # Ниндзюцу (Курода Рюхей): критический урон, кровотечения.
    TECH_NINJUTSU: (
        _c(crit_chance=0.05),
        _c(bleed=0.05),
        _c(crit_power=0.20),
        _c(dodge=0.03),
        _c(crit_chance=0.05, bleed=0.05),
        _c(first_strike=0.02),
        _c(crit_power=0.30),
        _c(bleed=0.10),
        _c(crit_chance=0.08),
        _c(crit_power=0.50, bleed=0.10),
    ),
    # Преодоление (Джинран): в бою становишься сильнее, чтобы победить; камень резонанса.
    TECH_OVERCOME: (
        _c(overcome=0.15),
        _c(durability=0.05),
        _c(overcome=0.10),
        _c(loss_save=0.03),
        _c(overcome=0.15),
        _c(reduction=0.04),
        _c(overcome=0.15),
        _c(despair=0.10),
        _c(overcome=0.15),
        _c(overcome=0.25, durability=0.10),
    ),
    # Киокушинкай: прочность и пробитие, игнор прочности и брони поглощения противника.
    TECH_KYOKUSHIN: (
        _c(durability=0.06),
        _c(pierce=0.10),
        _c(durability=0.06),
        _c(pierce=0.10),
        _c(block=0.04),
        _c(durability=0.08, pierce=0.05),
        _c(counter=0.04),
        _c(pierce=0.15),
        _c(durability=0.10),
        _c(pierce=0.20, durability=0.10),
    ),
    # Тхэквондо (Хансу): радиус атак — один статист бьёт сразу двоих.
    TECH_TAEKWONDO: (
        _c(cleave=0.06),
        _c(dodge=0.02),
        _c(cleave=0.06),
        _c(counter=0.03),
        _c(cleave=0.08),
        _c(opening=0.10),
        _c(cleave=0.08),
        _c(suppress=0.05),
        _c(cleave=0.10),
        _c(cleave=0.16),
    ),
    # Кулак Ма Тэсу: сильный удар, сила — «одной рукой сносить камни».
    TECH_MA_TAESU: (
        _c(attack=0.05),
        _c(crit_power=0.20),
        _c(attack=0.05),
        _c(pierce=0.05),
        _c(crit_chance=0.05),
        _c(attack=0.07),
        _c(opening=0.20),
        _c(crit_power=0.30),
        _c(attack=0.08),
        _c(attack=0.12, crit_power=0.40),
    ),
    # Удар одного шага (Гансоп): шаг и удар огромной силы — мастерство Скорости и Силы
    # усиливают первый удар (`opening_per_mastery` × ступени мастерства, см. Build).
    TECH_ONE_STEP: (
        _c(opening=0.20),
        _s(opening_per_mastery=0.05),
        _c(opening=0.20),
        _c(dodge=0.03),
        _s(opening_per_mastery=0.05),
        _c(sure_hit=0.05),
        _c(opening=0.30),
        _s(opening_per_mastery=0.05),
        _c(first_strike=0.02),
        _s({"opening": 0.50}, opening_per_mastery=0.10),
    ),
    # Руки-лезвия (Джин Чан): режущие удары — пробитие и кровотечение.
    TECH_BLADE_HANDS: (
        _c(bleed=0.05),
        _c(pierce=0.05),
        _c(bleed=0.05),
        _c(crit_chance=0.05),
        _c(pierce=0.08),
        _c(bleed=0.05, crit_power=0.15),
        _c(bleed=0.08),
        _c(sure_hit=0.05),
        _c(pierce=0.10),
        _c(bleed=0.12, pierce=0.10),
    ),
    # Муай-тай (Брэгдак): временно становиться сильнее.
    TECH_MUAY_THAI: (
        _c(rush=0.15, rush_rounds=2),
        _c(durability=0.04),
        _c(rush=0.10),
        _c(counter=0.03),
        _c(rush=0.15, rush_rounds=3),
        _c(attack=0.04),
        _c(rush=0.15),
        _c(reduction=0.04),
        _c(rush=0.15, rush_rounds=4),
        _c(rush=0.30, attack=0.06),
    ),
    # Полуночный меч: каждый следующий удар быстрее и задевает больше врагов — до 50 лун.
    TECH_MIDNIGHT: (
        _c(ramp=0.03, ramp_cap=0.15),
        _c(cleave=0.03),
        _c(ramp=0.02, ramp_cap=0.10),
        _c(dodge=0.02),
        _c(ramp=0.03, ramp_cap=0.15),
        _c(crit_chance=0.04),
        _c(ramp=0.03, ramp_cap=0.20),
        _c(cleave=0.05),
        _c(ramp=0.03, ramp_cap=0.20),
        _c(ramp=0.05, ramp_cap=0.40),
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


def technique_level_cost(next_level: int) -> int:
    return TECHNIQUE_LEVEL_COST_PER_LEVEL * next_level


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
