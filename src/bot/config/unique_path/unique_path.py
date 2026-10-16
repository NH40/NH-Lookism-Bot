"""Пути — 13 путей по 10 уровней, убеждение и квесты (конфиг). Формат уровней —
`config/development`.

Пользователь 2026-10-02 («одна из самых сложных механик»):
1. в зависимости от **потенциала и развития** приходит «подтверждение убеждений» — квест;
2. выполнил — **убеждение**, дальше копишь **фрагменты пути** (с босса **Ким Гапрена** на
   карте) и «Пробуждаешь путь» — путь **выпадает случайно** (2026-10-04: фрагменты нужны
   только для этого; второй квест «на путь» убран);
3. **10 уровней = 10 способностей**, уровни — за **очки пути**, которые даются за активность
   в боте (2026-10-04: «продумать так, чтобы путь качался только за 2 недели плотной игры»);
4. путь остаётся, пока не сброшен прогресс (патч, удаление банды, пробуждение); купившие
   несколько путей донатом переключают их в «Развитии».

Концепты путей — от пользователя (`docs/design/development_systems.md`, «Путь»), раскладка
способностей по уровням и числа — автор кода.
"""
from __future__ import annotations

from bot.constant.unique_path import PATH_SOURCE_DAILY
from bot.constant.dev_quest import (
    TASK_BOSS_WIN,
    TASK_BUILD,
    TASK_COLLECT,
    TASK_PERSONAL_TRAIN,
    TASK_RECRUIT,
    TASK_ROLL,
    TASK_SCHOOL_LESSON,
    TASK_TRAIN_EXTRAS,
    TASK_WAR_WIN,
    TASK_WIN_PVE,
    TASK_WIN_PVP,
)
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
    PATH_REFLECTION,
    PATH_SENSORY,
    PATH_SURE_HIT,
    PATH_TRAINING,
)
from bot.constant.characteristic import (
    POT_GANG_BOSS,
    POT_GEN_ZERO,
    POT_KING,
    POT_LEGEND,
    POT_MEMBER,
    POT_PEAK,
    POT_STRONG_KING,
    POT_WEAK_KING,
)


def _c(**kw) -> dict:
    return {"combat": kw}


def _e(**kw) -> dict:
    return {"eco": kw}


def _s(combat: dict | None = None, eco: dict | None = None, **special) -> dict:
    return {"combat": combat or {}, "eco": eco or {}, "special": special}


LEVELS: dict[str, tuple[dict, ...]] = {
    # Преодоление: чем больше урона впитал, тем сильнее — против толпы слабых.
    PATH_OVERCOME: (
        _c(overcome=0.20),
        _c(durability=0.05),
        _c(overcome=0.15),
        _c(loss_save=0.04),
        _c(overcome=0.20),
        _c(reduction=0.04),
        _c(overcome=0.20, durability=0.05),
        _c(counter=0.03),
        _c(overcome=0.20),
        _c(overcome=0.30, attack=0.05),
    ),
    # Отчаяние: шкала отчаяния против сильных — бафы и меньше потерь; путь боевой.
    PATH_DESPAIR: (
        _c(despair=0.20),
        _c(loss_save=0.03),
        _c(despair=0.15),
        _c(durability=0.05),
        _c(despair=0.20),
        _c(reduction=0.05),
        _c(despair=0.20, attack=0.03),
        _c(loss_save=0.05),
        _c(despair=0.20),
        _c(despair=0.30, durability=0.10),
    ),
    # Отражение: шкала копит полученный урон и возвращает его врагу.
    PATH_REFLECTION: (
        _c(reflect=0.10),
        _c(block=0.03),
        _c(reflect=0.10, reflect_every=3),
        _c(durability=0.05),
        _c(reflect=0.10),
        _c(reduction=0.04),
        _c(reflect=0.10),
        _c(counter=0.04),
        _c(reflect=0.15),
        _c(reflect=0.20, reflect_every=2),
    ),
    # Поглощение: чем сильнее бьют, тем больше запас и тем сильнее возврат.
    PATH_ABSORPTION: (
        _c(absorb_store=0.08, absorb_return=1.2),
        _c(durability=0.04),
        _c(absorb_store=0.06, absorb_return=0.2),
        _c(block=0.03),
        _c(absorb_store=0.06),
        _c(absorb_return=0.3),
        _c(reduction=0.04),
        _c(absorb_store=0.06),
        _c(absorb_return=0.3),
        _c(absorb_store=0.10, absorb_return=0.5),
    ),
    # Копирование: слияние способностей путей 5 последних противников в одну копию.
    PATH_COPY: (
        _s(memory_copy=0.15),
        _c(attack=0.03),
        _s(memory_copy=0.10),
        _c(dodge=0.02),
        _s(memory_copy=0.10),
        _c(durability=0.05),
        _s(memory_copy=0.10),
        _c(suppress=0.05),
        _s(memory_copy=0.10),
        _s(memory_copy=0.20),
    ),
    # Бесконечная техника (пользователь 2026-10-16): несколько уникальных техник одновременно —
    # активная в полную силу, дополнительные вполсилы (`INFINITE_EXTRA_TECHNIQUE_POWER`). Уровни
    # 1/4/7 — +1 техника (`extra_techniques` копится по уровням), 10 — все изученные (`all_techniques`).
    PATH_INFINITE: (
        _s(extra_techniques=1),
        _c(dodge=0.02),
        _c(attack=0.03),
        _s(extra_techniques=1),
        _c(counter=0.03),
        _c(dodge=0.02),
        _s(extra_techniques=1),
        _c(suppress=0.05),
        _c(attack=0.03),
        _s(all_techniques=True),
    ),
    # Предвидение: прогноз боя до боя и уклонение — сколько уклонится, сколько продолжит.
    PATH_FORESIGHT: (
        _e(foresight=1),
        _c(dodge=0.03),
        _c(flee=0.03),
        _e(foresight=2),
        _c(dodge=0.03),
        _c(loss_save=0.04),
        _c(counter=0.04),
        _e(foresight=3),
        _c(dodge=0.04),
        _c(dodge=0.05, suppress=0.05),
    ),
    # Сенсорика: метки на игроков, слежка за развитием, саботаж помеченных.
    PATH_SENSORY: (
        _e(marks=1),
        _e(logs=1),
        _e(marks=1),
        _s(sabotage_marked=True),
        _e(scout=1),
        _e(marks=1),
        _e(sabotage_chance=0.05),
        _e(logs=2),
        _e(marks=2),
        _e(scout=2, sabotage_loot=0.20),
    ),
    # Гарантированный удар: урон проходит даже сквозь уклонение.
    PATH_SURE_HIT: (
        _c(sure_hit=0.08),
        _c(crit_chance=0.03),
        _c(sure_hit=0.07),
        _c(pierce=0.05),
        _c(sure_hit=0.08),
        _c(attack=0.03),
        _c(sure_hit=0.08),
        _c(pierce=0.05),
        _c(sure_hit=0.09),
        _c(sure_hit=0.10, no_dodge=True),
    ),
    # Адаптация: терпишь, терпишь — потом огромный импакт (как родословная Софии).
    PATH_ADAPTATION: (
        _c(adapt_threshold=0.30, adapt_bonus=0.20),
        _c(adapt_guard=0.05),
        _c(adapt_bonus=0.15),
        _c(durability=0.05),
        _c(adapt_bonus=0.20),
        _c(adapt_guard=0.05),
        _c(adapt_threshold=0.25),
        _c(adapt_bonus=0.20),
        _c(adapt_guard=0.05),
        _c(adapt_bonus=0.35),
    ),
    # Бесконечная тренировка: статист учится у нескольких учителей сразу.
    PATH_TRAINING: (
        _e(extras_training=3),
        _e(extras_extra_roll=0.10),
        _e(extras_training_cooldown=0.10),
        _e(extras_training=3),
        _e(extras_extra_roll=0.10),
        _e(dev_points=0.10),
        _e(extras_training_cooldown=0.10),
        _e(extras_extra_roll=0.15),
        _e(extras_training=4),
        _e(extras_extra_roll=0.20, extras_training=5),
    ),
    # Уклонение: автоуклонения, уклонение в «невозможных» ситуациях.
    PATH_EVASION: (
        _c(dodge=0.04),
        _c(flee=0.02),
        _c(dodge=0.04),
        _c(counter=0.03),
        _c(dodge=0.05),
        _c(reduction=0.03),
        _c(dodge=0.05),
        _c(dodge=0.05),
        _c(loss_save=0.04),
        _c(dodge=0.08, counter=0.04),
    ),
    # Бизнесмена: бизнес — больше заработок.
    PATH_BUSINESS: (
        _e(income=0.05),
        _e(storage_hours=4),
        _e(upgrade_discount=0.10),
        _e(income=0.05),
        _e(build_discount=0.10),
        _e(tax_relief=0.10),
        _e(income=0.06),
        _e(storage_hours=8),
        _e(upgrade_discount=0.10, build_discount=0.10),
        _e(income=0.12),
    ),
}

# «Подтверждение убеждений» приходит, когда сумма рангов четырёх характеристик (индексы в
# RANK_LADDER) достигает порога — у кого потенциал выше, тому раньше (пользователь: «в
# зависимости от потенциала и развития игрока»).
CONVICTION_RANK_SUM: dict[str, int] = {
    POT_MEMBER: 88,
    POT_GANG_BOSS: 80,
    POT_WEAK_KING: 72,
    POT_KING: 64,
    POT_STRONG_KING: 56,
    POT_GEN_ZERO: 48,
    POT_PEAK: 40,
    POT_LEGEND: 32,
}
CONVICTION_QUEST: dict[str, int] = {TASK_WIN_PVE: 10, TASK_PERSONAL_TRAIN: 5, TASK_BOSS_WIN: 1}
# «Пробудить путь»: столько фрагментов пути (с Ким Гапрена) после квеста убеждения.
PATH_AWAKEN_FRAGMENTS = 100

# Уровни пути — за очки пути. 2-й — 240, 10-й — 1 200; до 10-го — 6 480 очков.
PATH_LEVEL_COST_PER_LEVEL = 120

# Очки пути за активность (начисляются, только пока путь пробуждён). Источник → (очки,
# минимальный интервал между засчитанными событиями, сек). Защита от абуза — интервал на
# КАЖДЫЙ источник: частое повторение одного действия (PvP с твинком, сбор дохода раз в
# минуту, крутка пачкой) засчитывается не чаще интервала, а сами действия и так ограничены
# своими КД/ресурсами. Темп (решение автора кода, пользователь — «2 недели плотной игры»):
# плотная игра ≈ 450 очков в день → 10-й уровень за ~14 дней; теоретический максимум (16 ч
# в сутки, каждое действие по интервалу, император с войнами) ≈ 690 в день — не быстрее ~9
# дней.
PATH_POINT_SOURCES: dict[str, tuple[int, int]] = {
    TASK_PERSONAL_TRAIN: (6, 55 * 60),
    TASK_TRAIN_EXTRAS: (3, 55 * 60),
    TASK_SCHOOL_LESSON: (4, 55 * 60),
    TASK_WIN_PVE: (4, 30 * 60),
    TASK_WIN_PVP: (8, 60 * 60),
    TASK_BOSS_WIN: (12, 60 * 60),
    TASK_WAR_WIN: (20, 6 * 60 * 60),
    TASK_COLLECT: (2, 2 * 60 * 60),
    TASK_BUILD: (3, 60 * 60),
    TASK_RECRUIT: (2, 60 * 60),
    TASK_ROLL: (1, 30 * 60),
    PATH_SOURCE_DAILY: (10, 20 * 60 * 60),
}


def path_level_cost(next_level: int) -> int:
    return PATH_LEVEL_COST_PER_LEVEL * next_level


# Путь тренировок (пользователь 2026-10-16): КПД всех тренировок растёт от дней на пути и от
# каждой тренировки, потолок — по уровню пути. КПД: больше очков развития и шансов, короче КД,
# дешевле тренировка техник, быстрее очки пути.
TRAINING_KPD_PER_DAY = 0.02
TRAINING_KPD_PER_REP = 0.005
TRAINING_KPD_CAP_PER_LEVEL = 0.05  # 10-й уровень — до +50%
TRAINING_KPD_EXTRAS_PP = 20  # КПД 1.0 = +20 п.п. к шансам тренировки статистов и занятий школ

# Сила дополнительных техник пути Бесконечной техники (активная — 100%).
INFINITE_EXTRA_TECHNIQUE_POWER = 0.5

PATH_SWAP_COOLDOWN_SECONDS = 15 * 60
# Предвидение: сколько симуляций для прогноза по уровням (точность растёт с уровнем).
FORESIGHT_SIMULATIONS: dict[int, int] = {1: 8, 2: 16, 3: 40}
